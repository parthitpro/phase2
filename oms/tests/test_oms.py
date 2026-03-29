"""
Unit Tests for Order Management System
Tests for contact cleaning logic and order submission
"""
import unittest
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import ContactCleaner


class TestContactCleaning(unittest.TestCase):
    """Test cases for contact cleaning utility"""
    
    def setUp(self):
        self.cleaner = ContactCleaner()
    
    # Phone Standardization Tests
    def test_standardize_phone_10_digit(self):
        """Test standardizing 10-digit Indian numbers"""
        self.assertEqual(self.cleaner.standardize_phone('9876543210'), '+919876543210')
        self.assertEqual(self.cleaner.standardize_phone('8765432109'), '+918765432109')
    
    def test_standardize_phone_with_plus91(self):
        """Test phone numbers already with +91"""
        self.assertEqual(self.cleaner.standardize_phone('+919876543210'), '+919876543210')
        self.assertEqual(self.cleaner.standardize_phone('919876543210'), '+919876543210')
    
    def test_standardize_phone_with_leading_zero(self):
        """Test phone numbers with leading zero"""
        self.assertEqual(self.cleaner.standardize_phone('09876543210'), '+919876543210')
    
    def test_standardize_phone_with_spaces_dashes(self):
        """Test phone numbers with spaces and dashes"""
        self.assertEqual(self.cleaner.standardize_phone('98765 43210'), '+919876543210')
        self.assertEqual(self.cleaner.standardize_phone('98765-43210'), '+919876543210')
        self.assertEqual(self.cleaner.standardize_phone('9876 543 210'), '+919876543210')
    
    def test_standardize_phone_service_numbers(self):
        """Test that service numbers are rejected"""
        self.assertIsNone(self.cleaner.standardize_phone('100'))
        self.assertIsNone(self.cleaner.standardize_phone('199'))
        self.assertIsNone(self.cleaner.standardize_phone('108'))
    
    def test_standardize_phone_invalid(self):
        """Test invalid phone numbers"""
        self.assertIsNone(self.cleaner.standardize_phone('12345'))  # Too short
        self.assertIsNone(self.cleaner.standardize_phone('1234567890'))  # Starts with 1
    
    # Name Extraction Tests
    def test_extract_name_first_last(self):
        """Test extracting name from first and last name"""
        self.assertEqual(self.cleaner.extract_name('John', 'Doe', ''), 'John Doe')
        self.assertEqual(self.cleaner.extract_name('Rajesh', 'Kumar', ''), 'Rajesh Kumar')
    
    def test_extract_name_file_as_fallback(self):
        """Test extracting name from File As field"""
        self.assertEqual(self.cleaner.extract_name('', '', 'John Doe'), 'John Doe')
        self.assertEqual(self.cleaner.extract_name('', '', 'ABC Enterprises'), 'Abc Enterprises')
    
    def test_extract_name_phone_in_name_field(self):
        """Test rejection of phone numbers in name fields"""
        self.assertIsNone(self.cleaner.extract_name('9876543210', '', ''))
        self.assertIsNone(self.cleaner.extract_name('+919876543210', '', ''))
        self.assertIsNone(self.cleaner.extract_name('', '', '1234567890'))
    
    def test_extract_name_address_keywords(self):
        """Test rejection of addresses in name fields"""
        self.assertIsNone(self.cleaner.extract_name('Main Road', '', ''))
        self.assertIsNone(self.cleaner.extract_name('123 Street', '', ''))
        self.assertIsNone(self.cleaner.extract_name('Floor 5', '', ''))
        self.assertIsNone(self.cleaner.extract_name('Apt 101', '', ''))
    
    def test_extract_name_import_notes(self):
        """Test rejection of import notes"""
        self.assertIsNone(self.cleaner.extract_name('Imported on 2024-01-01', '', ''))
        self.assertIsNone(self.cleaner.extract_name('myContacts', '', ''))
    
    def test_extract_name_service_keywords(self):
        """Test rejection of service entries"""
        self.assertIsNone(self.cleaner.extract_name('Bank Customer Care', '', ''))
        self.assertIsNone(self.cleaner.extract_name('Jio Store', '', ''))
        self.assertIsNone(self.cleaner.extract_name('Hospital Emergency', '', ''))
    
    # Keyword Detection Tests
    def test_contains_address_keywords(self):
        """Test address keyword detection"""
        self.assertTrue(self.cleaner.contains_address_keywords('123 Main Rd'))
        self.assertTrue(self.cleaner.contains_address_keywords('Park Street'))
        self.assertTrue(self.cleaner.contains_address_keywords('5th Floor'))
        self.assertTrue(self.cleaner.contains_address_keywords('Apt 4B'))
        self.assertFalse(self.cleaner.contains_address_keywords('John Smith'))
    
    def test_contains_service_keywords(self):
        """Test service keyword detection"""
        self.assertTrue(self.cleaner.contains_service_keywords('Bank of India'))
        self.assertTrue(self.cleaner.contains_service_keywords('Customer Care'))
        self.assertTrue(self.cleaner.contains_service_keywords('Railway Station'))
        self.assertTrue(self.cleaner.contains_service_keywords('Ambulance Service'))
        self.assertFalse(self.cleaner.contains_service_keywords('Rajesh Kumar'))
    
    def test_is_phone_only_string(self):
        """Test phone-only string detection"""
        self.assertTrue(self.cleaner.is_phone_only_string('9876543210'))
        self.assertTrue(self.cleaner.is_phone_only_string('+91-98765-43210'))
        self.assertTrue(self.cleaner.is_phone_only_string('123 456 7890'))
        self.assertFalse(self.cleaner.is_phone_only_string('John Doe'))
        self.assertFalse(self.cleaner.is_phone_only_string('123 Main St'))


class TestOrderLogic(unittest.TestCase):
    """Test cases for order business logic"""
    
    def test_pack_size_calculation(self):
        """Test pack size price calculation"""
        # Simulating Product.get_price_for_pack logic
        retail_price_per_kg = 340.0
        
        # 250g pack
        price_250g = retail_price_per_kg * 0.25
        self.assertEqual(price_250g, 85.0)
        
        # 500g pack
        price_500g = retail_price_per_kg * 0.5
        self.assertEqual(price_500g, 170.0)
        
        # 1kg pack
        price_1kg = retail_price_per_kg * 1.0
        self.assertEqual(price_1kg, 340.0)
    
    def test_wholesale_discount(self):
        """Test wholesale discount calculation"""
        retail_price = 340.0
        wholesale_discount = 15.0
        
        discounted_price = retail_price * (1 - wholesale_discount / 100)
        self.assertEqual(discounted_price, 289.0)
    
    def test_order_total_calculation(self):
        """Test order total calculation"""
        items = [
            {'price': 85.0, 'quantity': 2},   # 250g x 2
            {'price': 170.0, 'quantity': 1},  # 500g x 1
            {'price': 340.0, 'quantity': 1},  # 1kg x 1
        ]
        
        total = sum(item['price'] * item['quantity'] for item in items)
        self.assertEqual(total, 680.0)


if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)
