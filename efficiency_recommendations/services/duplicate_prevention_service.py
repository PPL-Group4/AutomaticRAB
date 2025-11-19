class DuplicatePreventionService:
    
    @staticmethod
    def remove_duplicates(notifications):
        if not notifications:
            return []
        
        seen = set()
        unique_notifications = []
        
        for notification in notifications:
            # Create a unique key based on type and message
            key = (notification.get('type', ''), notification.get('message', ''))
            
            if key not in seen:
                seen.add(key)
                unique_notifications.append(notification)
        
        return unique_notifications
    
    @staticmethod
    def has_duplicates(notifications):
        if not notifications:
            return False
        
        seen = set()
        
        for notification in notifications:
            key = (notification.get('type', ''), notification.get('message', ''))
            
            if key in seen:
                return True
            
            seen.add(key)
        
        return False
    
    @staticmethod
    def get_duplicate_count(notifications):
        if not notifications:
            return 0
        
        seen = {}
        
        for notification in notifications:
            key = (notification.get('type', ''), notification.get('message', ''))
            seen[key] = seen.get(key, 0) + 1
        
        # Count how many duplicates (entries that appear more than once)
        duplicate_count = sum(1 for count in seen.values() if count > 1)
        
        return duplicate_count
