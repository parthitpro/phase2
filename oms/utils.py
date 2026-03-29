"""
Contact Import & Cleaning Utility
Handles messy Google Contacts CSV imports with robust data validation
"""
import re
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime


class ContactCleaner:
    """Utility class for cleaning and validating contact data from Google Contacts CSV"""
    
    # Service numbers and keywords to ignore
    SERVICE_KEYWORDS = [
        '100', '199', '101', '102', '108', '112',  # Emergency numbers
        'jio', 'airtel', 'vodafone', 'idea',  # Carrier services
        'railway', 'train', 'airport',  # Transport
        'ambulance', 'hospital', 'doctor',  # Medical
        'bank', 'atm', 'credit', 'debit',  # Financial
        'care', 'service', 'support', 'helpline',  # Customer service
        'police', 'fire',  # Emergency services
        'mycontacts', 'starred', 'imported'  # Google Contacts labels
    ]
    
    # Address keywords to filter out non-person entries
    ADDRESS_KEYWORDS = [
        'rd', 'road', 'st', 'street', 'lane', 'floor', 'apt', 'bldg',
        'building', 'house', 'office', 'shop', 'market', 'area',
        'colony', 'nagar', 'park', 'view', 'heights', 'residency'
    ]
    
    # Regex patterns
    PHONE_ONLY_PATTERN = re.compile(r'^[\+]?[\d\s\-\(\)]+$')
    INDIAN_PHONE_PATTERN = re.compile(r'^\+91\d{10}$')
    CLEAN_PHONE_PATTERN = re.compile(r'[\d\+]+')
    
    def __init__(self):
        self.stats = {
            'new': 0,
            'updates_pending': 0,
            'unchanged': 0,
            'skipped_invalid': 0,
            'skipped_service': 0,
            'skipped_address': 0
        }
    
    def is_phone_only_string(self, text: str) -> bool:
        """Check if string looks like a phone number only (no alphabetic characters)"""
        if not text:
            return False
        cleaned = text.strip()
        return bool(self.PHONE_ONLY_PATTERN.match(cleaned))
    
    def contains_address_keywords(self, text: str) -> bool:
        """Check if text contains address-related keywords"""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.ADDRESS_KEYWORDS)
    
    def contains_service_keywords(self, text: str) -> bool:
        """Check if text contains service-related keywords"""
        if not text:
            return False
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.SERVICE_KEYWORDS)
    
    def extract_name(self, first_name: str, last_name: str, file_as: str) -> Optional[str]:
        """
        Extract and clean name from various fields.
        Returns None if the entry should be ignored.
        """
        # Try First Name + Last Name first
        if first_name and first_name.strip():
            name_parts = []
            if first_name.strip():
                name_parts.append(first_name.strip())
            if last_name and last_name.strip():
                name_parts.append(last_name.strip())
            
            candidate_name = ' '.join(name_parts)
            
            # Validate the name
            if self.is_phone_only_string(candidate_name):
                return None
            if self.contains_address_keywords(candidate_name):
                return None
            if self.contains_service_keywords(candidate_name):
                return None
            
            # Check for import notes
            if 'imported on' in candidate_name.lower() or 'mycontacts' in candidate_name.lower():
                return None
            
            return candidate_name.title()
        
        # Fallback to File As field
        if file_as and file_as.strip():
            candidate_name = file_as.strip()
            
            # Same validations
            if self.is_phone_only_string(candidate_name):
                return None
            if self.contains_address_keywords(candidate_name):
                return None
            if self.contains_service_keywords(candidate_name):
                return None
            if 'imported on' in candidate_name.lower() or 'mycontacts' in candidate_name.lower():
                return None
            
            return candidate_name.title()
        
        return None
    
    def standardize_phone(self, phone: str) -> Optional[str]:
        """
        Standardize phone number to +91XXXXXXXXXX format.
        Returns None if invalid or service number.
        """
        if not phone:
            return None
        
        # Clean the phone number - extract only digits and +
        cleaned = ''.join(filter(str.isdigit, phone))
        
        # Check if it's a service number before processing
        phone_lower = phone.lower()
        if self.contains_service_keywords(phone_lower):
            return None
        
        # Handle different formats
        if len(cleaned) == 10:
            # Indian number without country code
            if cleaned.startswith('6') or cleaned.startswith('7') or \
               cleaned.startswith('8') or cleaned.startswith('9'):
                return f'+91{cleaned}'
        elif len(cleaned) == 12:
            # Already has country code
            if cleaned.startswith('91'):
                return f'+{cleaned}'
        elif len(cleaned) == 11:
            # Might have leading 0
            if cleaned.startswith('0') and len(cleaned[1:]) == 10:
                rest = cleaned[1:]
                if rest.startswith('6') or rest.startswith('7') or \
                   rest.startswith('8') or rest.startswith('9'):
                    return f'+91{rest}'
        
        return None
    
    def extract_phones_from_row(self, row: pd.Series) -> List[str]:
        """
        Extract all valid phone numbers from a row.
        Checks Phone 1-5 Value columns and even Name columns (phones sometimes end up there).
        """
        phones = []
        
        # Check all phone columns
        phone_columns = [col for col in row.index if 'phone' in col.lower() and 'value' in col.lower()]
        
        for col in phone_columns:
            phone_val = row.get(col)
            if pd.notna(phone_val) and str(phone_val).strip():
                standardized = self.standardize_phone(str(phone_val))
                if standardized and self.INDIAN_PHONE_PATTERN.match(standardized):
                    phones.append(standardized)
        
        # Also check name fields for phone numbers (common in messy data)
        name_fields = ['First Name', 'Last Name', 'File As']
        for field in name_fields:
            if field in row.index:
                val = row.get(field)
                if pd.notna(val) and str(val).strip():
                    val_str = str(val).strip()
                    if self.is_phone_only_string(val_str):
                        standardized = self.standardize_phone(val_str)
                        if standardized and self.INDIAN_PHONE_PATTERN.match(standardized):
                            phones.append(standardized)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_phones = []
        for phone in phones:
            if phone not in seen:
                seen.add(phone)
                unique_phones.append(phone)
        
        return unique_phones
    
    def process_csv(self, csv_file_path: str) -> Tuple[List[Dict], Dict]:
        """
        Process a Google Contacts CSV file and return cleaned contacts with stats.
        
        Returns:
            Tuple of (list of cleaned contact dicts, statistics dict)
        """
        try:
            # Read CSV with proper encoding
            df = pd.read_csv(csv_file_path, encoding='utf-8', dtype=str)
        except UnicodeDecodeError:
            # Fallback to latin-1 encoding
            df = pd.read_csv(csv_file_path, encoding='latin-1', dtype=str)
        
        cleaned_contacts = []
        
        for idx, row in df.iterrows():
            # Extract name
            first_name = row.get('First Name', '')
            last_name = row.get('Last Name', '')
            file_as = row.get('File As', '')
            
            name = self.extract_name(first_name, last_name, file_as)
            if not name:
                self.stats['skipped_invalid'] += 1
                continue
            
            # Extract phones
            phones = self.extract_phones_from_row(row)
            
            if not phones:
                self.stats['skipped_invalid'] += 1
                continue
            
            # Create contact record
            contact = {
                'name': name,
                'phone_primary': phones[0],
                'phone_secondary': phones[1] if len(phones) > 1 else None,
                'all_phones': phones,  # For merge detection
                'type': 'retail',  # Default, can be updated later
                'discount_percent': 0.0
            }
            
            cleaned_contacts.append(contact)
            self.stats['new'] += 1  # Will be adjusted during DB merge
        
        return cleaned_contacts, self.stats
    
    def merge_contacts_by_phone(self, contacts: List[Dict]) -> List[Dict]:
        """
        Merge contacts that share any phone number.
        Returns deduplicated list.
        """
        phone_to_contact = {}
        merged = []
        
        for contact in contacts:
            primary = contact['phone_primary']
            
            if primary in phone_to_contact:
                # Merge with existing contact
                existing = phone_to_contact[primary]
                
                # Update secondary phone if we have a new one
                if contact['phone_secondary'] and not existing.get('phone_secondary'):
                    existing['phone_secondary'] = contact['phone_secondary']
                
                self.stats['new'] -= 1  # Decrement as this is a merge
            else:
                phone_to_contact[primary] = contact
                merged.append(contact)
        
        return merged


def process_contact_upload(csv_file_path: str, db_session, CustomerModel) -> Dict:
    """
    Main function to process contact upload.
    
    Args:
        csv_file_path: Path to the uploaded CSV file
        db_session: SQLAlchemy database session
        CustomerModel: Customer model class
    
    Returns:
        Dictionary with counts: {'new': count, 'updates_pending': count, 'unchanged': count}
    """
    cleaner = ContactCleaner()
    
    # Step 1: Parse and clean CSV
    cleaned_contacts, _ = cleaner.process_csv(csv_file_path)
    
    # Step 2: Merge contacts with duplicate phones
    cleaned_contacts = cleaner.merge_contacts_by_phone(cleaned_contacts)
    
    # Step 3: Process against database
    results = {
        'new': 0,
        'updates_pending': 0,
        'unchanged': 0,
        'updated': 0
    }
    
    for contact in cleaned_contacts:
        phone = contact['phone_primary']
        name = contact['name']
        
        # Check if phone exists in database
        existing_customer = CustomerModel.query.filter_by(phone_primary=phone).first()
        
        if existing_customer:
            # Compare names
            if existing_customer.name.lower() == name.lower():
                # Names match - just update timestamp
                existing_customer.last_updated = datetime.utcnow()
                results['unchanged'] += 1
            else:
                # Names differ - mark for review
                existing_customer.contact_update_status = 'pending_review'
                existing_customer.last_updated = datetime.utcnow()
                results['updates_pending'] += 1
        else:
            # New customer
            new_customer = CustomerModel(
                name=name,
                phone_primary=phone,
                phone_secondary=contact.get('phone_secondary'),
                type=contact['type'],
                discount_percent=contact['discount_percent'],
                contact_update_status='approved',
                last_updated=datetime.utcnow()
            )
            db_session.add(new_customer)
            results['new'] += 1
    
    # Commit all changes
    db_session.commit()
    
    return results


# Standalone test function for unit testing
def test_contact_cleaning():
    """Unit tests for contact cleaning logic"""
    cleaner = ContactCleaner()
    
    # Test phone standardization
    assert cleaner.standardize_phone('9876543210') == '+919876543210'
    assert cleaner.standardize_phone('+919876543210') == '+919876543210'
    assert cleaner.standardize_phone('09876543210') == '+919876543210'
    assert cleaner.standardize_phone('100') is None  # Service number
    assert cleaner.standardize_phone('Jio Care') is None  # Service keyword
    
    # Test name extraction
    assert cleaner.extract_name('John', 'Doe', '') == 'John Doe'
    assert cleaner.extract_name('', '', 'John Doe') == 'John Doe'
    assert cleaner.extract_name('1234567890', '', '') is None  # Phone in name
    assert cleaner.extract_name('Main Road', '', '') is None  # Address in name
    assert cleaner.extract_name('Imported on 2024-01-01', '', '') is None  # Import note
    
    # Test address keyword detection
    assert cleaner.contains_address_keywords('123 Main Rd') is True
    assert cleaner.contains_address_keywords('John Doe') is False
    
    # Test service keyword detection
    assert cleaner.contains_service_keywords('Bank Customer Care') is True
    assert cleaner.contains_service_keywords('John Smith') is False
    
    print("All tests passed!")


if __name__ == '__main__':
    test_contact_cleaning()
