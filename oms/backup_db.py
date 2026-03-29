"""
Database Backup Utility for OMS
Performs automated MySQL database backups using mysqldump
"""
import os
import subprocess
import datetime
import gzip
import shutil
from pathlib import Path


class DatabaseBackup:
    """Handles database backup operations"""
    
    def __init__(self, db_name, db_user, db_password, db_host='localhost', backup_dir=None):
        self.db_name = db_name
        self.db_user = db_user
        self.db_password = db_password
        self.db_host = db_host
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), 
            'backups'
        )
        
        # Ensure backup directory exists
        Path(self.backup_dir).mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, compress=True):
        """
        Create a database backup using mysqldump
        
        Args:
            compress: If True, compress the backup with gzip
            
        Returns:
            Tuple of (success: bool, filepath: str or None, message: str)
        """
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'{self.db_name}_backup_{timestamp}.sql'
        filepath = os.path.join(self.backup_dir, filename)
        
        # Build mysqldump command
        cmd = [
            'mysqldump',
            f'--host={self.db_host}',
            f'--user={self.db_user}',
            f'--password={self.db_password}',
            '--single-transaction',
            '--routines',
            '--triggers',
            '--events',
            self.db_name
        ]
        
        try:
            # Execute mysqldump
            with open(filepath, 'w', encoding='utf-8') as f:
                result = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    check=True
                )
            
            if compress:
                # Compress the backup
                compressed_path = filepath + '.gz'
                with open(filepath, 'rb') as f_in:
                    with gzip.open(compressed_path, 'wb') as f_out:
                        shutil.copyfileobj(f_in, f_out)
                
                # Remove uncompressed file
                os.remove(filepath)
                filepath = compressed_path
            
            return True, filepath, f'Backup created successfully: {filepath}'
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode('utf-8') if e.stderr else str(e)
            return False, None, f'mysqldump failed: {error_msg}'
        except Exception as e:
            return False, None, f'Backup failed: {str(e)}'
    
    def list_backups(self, limit=10):
        """List recent backups"""
        backups = []
        
        for filename in sorted(os.listdir(self.backup_dir), reverse=True):
            if filename.startswith(f'{self.db_name}_backup_'):
                filepath = os.path.join(self.backup_dir, filename)
                size = os.path.getsize(filepath)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                
                backups.append({
                    'filename': filename,
                    'filepath': filepath,
                    'size': size,
                    'size_human': self._format_size(size),
                    'created': mtime
                })
                
                if len(backups) >= limit:
                    break
        
        return backups
    
    def restore_backup(self, backup_file):
        """
        Restore database from a backup file
        
        Args:
            backup_file: Path to the backup file (.sql or .sql.gz)
            
        Returns:
            Tuple of (success: bool, message: str)
        """
        if not os.path.exists(backup_file):
            return False, f'Backup file not found: {backup_file}'
        
        try:
            # Determine if file is compressed
            is_compressed = backup_file.endswith('.gz')
            
            # Build mysql restore command
            cmd = [
                'mysql',
                f'--host={self.db_host}',
                f'--user={self.db_user}',
                f'--password={self.db_password}',
                self.db_name
            ]
            
            if is_compressed:
                # Decompress and pipe to mysql
                gunzip_cmd = ['gunzip', '-c', backup_file]
                gunzip_proc = subprocess.Popen(gunzip_cmd, stdout=subprocess.PIPE)
                mysql_proc = subprocess.Popen(cmd, stdin=gunzip_proc.stdout, stderr=subprocess.PIPE)
                gunzip_proc.stdout.close()
                _, error = mysql_proc.communicate()
            else:
                # Read SQL file directly
                with open(backup_file, 'r', encoding='utf-8') as f:
                    result = subprocess.run(
                        cmd,
                        stdin=f,
                        stderr=subprocess.PIPE,
                        check=True
                    )
                    error = result.stderr
            
            if mysql_proc.returncode == 0 if is_compressed else True:
                return True, 'Database restored successfully'
            else:
                return False, f'Restore failed: {error.decode("utf-8") if error else "Unknown error"}'
                
        except Exception as e:
            return False, f'Restore failed: {str(e)}'
    
    def cleanup_old_backups(self, days_to_keep=30):
        """
        Delete backups older than specified days
        
        Args:
            days_to_keep: Number of days to retain backups
            
        Returns:
            Number of files deleted
        """
        deleted_count = 0
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days_to_keep)
        
        for filename in os.listdir(self.backup_dir):
            if filename.startswith(f'{self.db_name}_backup_'):
                filepath = os.path.join(self.backup_dir, filename)
                mtime = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
                
                if mtime < cutoff_date:
                    os.remove(filepath)
                    deleted_count += 1
        
        return deleted_count
    
    def _format_size(self, size_bytes):
        """Format file size in human-readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"


def main():
    """Main function for standalone backup execution"""
    # Configuration - In production, use environment variables
    DB_NAME = os.environ.get('DB_NAME', 'oms_db')
    DB_USER = os.environ.get('DB_USER', 'root')
    DB_PASSWORD = os.environ.get('DB_PASSWORD', 'password')
    DB_HOST = os.environ.get('DB_HOST', 'localhost')
    
    backup = DatabaseBackup(
        db_name=DB_NAME,
        db_user=DB_USER,
        db_password=DB_PASSWORD,
        db_host=DB_HOST
    )
    
    print(f'Starting backup of database: {DB_NAME}')
    success, filepath, message = backup.create_backup()
    
    if success:
        print(f'✓ {message}')
        
        # Cleanup old backups
        deleted = backup.cleanup_old_backups(days_to_keep=30)
        if deleted > 0:
            print(f'✓ Cleaned up {deleted} old backup(s)')
    else:
        print(f'✗ {message}')
        exit(1)


if __name__ == '__main__':
    main()
