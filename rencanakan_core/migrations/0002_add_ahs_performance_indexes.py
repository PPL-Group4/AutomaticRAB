from django.db import migrations


def add_indexes_if_table_exists(apps, schema_editor):
    """Add indexes only if ahs table exists"""
    with schema_editor.connection.cursor() as cursor:
        # Check if table exists
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'ahs'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            # Add indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ahs_code ON ahs(code)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ahs_name ON ahs(name(255))")


def remove_indexes_if_table_exists(apps, schema_editor):
    """Remove indexes only if ahs table exists"""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("""
            SELECT COUNT(*) 
            FROM information_schema.tables 
            WHERE table_schema = DATABASE() 
            AND table_name = 'ahs'
        """)
        table_exists = cursor.fetchone()[0] > 0
        
        if table_exists:
            cursor.execute("DROP INDEX IF EXISTS idx_ahs_code ON ahs")
            cursor.execute("DROP INDEX IF EXISTS idx_ahs_name ON ahs")


class Migration(migrations.Migration):

    dependencies = [
        ('rencanakan_core', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(
            add_indexes_if_table_exists, 
            remove_indexes_if_table_exists
        ),
    ]