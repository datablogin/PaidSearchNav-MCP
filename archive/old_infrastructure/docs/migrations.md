# Database Migration Guide

This guide covers database migration development, testing, and deployment for PaidSearchNav.

## Overview

Database migrations are managed using [Alembic](https://alembic.sqlalchemy.org/), which provides version control for database schemas. All migrations are located in `paidsearchnav/storage/migrations/versions/`.

## Migration Development

### Creating a New Migration

1. **Make changes to models first**:
   ```python
   # Edit paidsearchnav/storage/models.py
   # Add new columns, tables, indexes, etc.
   ```

2. **Generate migration script**:
   ```bash
   python -m alembic revision --autogenerate -m "Description of changes"
   ```

3. **Review generated migration**:
   - Check the generated SQL operations
   - Ensure both `upgrade()` and `downgrade()` functions are correct
   - Add any custom logic needed
   - Test with sample data

4. **Test the migration**:
   ```bash
   # Run tests
   pytest tests/unit/storage/test_migrations.py -v
   
   # Manual testing
   python -m alembic upgrade head
   python -m alembic downgrade -1
   python -m alembic upgrade head
   ```

### Migration Best Practices

#### Naming Conventions
- Use descriptive migration names: `001_create_users_table.py`
- Include revision number for ordering: `002_add_customer_indexes.py`
- Use verb-noun format: `003_add_job_executions_table.py`

#### Schema Changes
- **Adding columns**: Always make new columns nullable or provide defaults
- **Removing columns**: Consider deprecation period before removal
- **Renaming columns**: Use a multi-step process with data migration
- **Indexes**: Create indexes concurrently when possible (PostgreSQL)

#### Data Migrations
```python
def upgrade():
    # Schema changes first
    op.add_column('users', sa.Column('new_field', sa.String(50)))
    
    # Data migration
    connection = op.get_bind()
    connection.execute(text("""
        UPDATE users SET new_field = 'default_value' 
        WHERE new_field IS NULL
    """))
    
    # Make column non-nullable after data migration
    op.alter_column('users', 'new_field', nullable=False)
```

#### Rollback Considerations
- Always implement `downgrade()` function
- Test rollbacks thoroughly
- Consider data loss implications
- Document any irreversible operations

## Testing Migrations

### Automated Tests

The project includes comprehensive migration tests in `tests/unit/storage/test_migrations.py`:

- **Forward/Backward Tests**: Verify upgrade and downgrade work correctly
- **Idempotency Tests**: Ensure migrations can be run multiple times safely
- **Data Preservation Tests**: Check that existing data is preserved
- **Performance Tests**: Monitor migration execution time
- **Schema Compatibility Tests**: Verify foreign keys, indexes, and constraints

### Running Migration Tests

```bash
# Run all migration tests
pytest tests/unit/storage/test_migrations.py -v

# Run specific test categories
pytest tests/unit/storage/test_migrations.py::TestMigrationUpDown -v
pytest tests/unit/storage/test_migrations.py::TestMigrationIdempotency -v

# Run with PostgreSQL (requires TEST_POSTGRES_URL)
export TEST_POSTGRES_URL=postgresql://user:pass@localhost:5432/testdb
pytest tests/unit/storage/test_migrations.py::TestMigrationWithPostgreSQL -v
```

### Manual Testing

```bash
# Test upgrade path
python -m alembic upgrade head

# Test specific revision
python -m alembic upgrade 003

# Test downgrade
python -m alembic downgrade -1
python -m alembic downgrade base

# Show current revision
python -m alembic current

# Show migration history
python -m alembic history --verbose
```

## CI/CD Integration

### GitHub Actions Workflow

The `migration-tests.yml` workflow automatically tests migrations on:
- Push to main/develop branches
- Pull requests affecting migration files
- Changes to models or migration tests

### Test Matrix
- **SQLite**: Development environment testing
- **PostgreSQL**: Production environment testing  
- **Performance**: Migration execution time benchmarks
- **Compatibility**: Testing across Python versions
- **Security**: Scanning for sensitive data or SQL injection risks

### Failure Handling
- Automatic issue creation on test failures
- Detailed logs for debugging
- Security scan reports
- Performance regression detection

## Production Deployment

### Pre-deployment Checklist

1. **Review migration thoroughly**:
   - [ ] Schema changes are correct
   - [ ] Downgrade function works
   - [ ] Data migration logic is sound
   - [ ] Performance impact assessed

2. **Test in staging**:
   - [ ] Run migration on staging data
   - [ ] Verify application functionality
   - [ ] Test rollback procedure
   - [ ] Check performance metrics

3. **Backup considerations**:
   - [ ] Database backup taken
   - [ ] Recovery procedure documented
   - [ ] Rollback plan prepared

### Deployment Process

1. **Maintenance mode** (if needed for large migrations)
2. **Database backup**
3. **Run migration**:
   ```bash
   python -m alembic upgrade head
   ```
4. **Verify success**:
   ```bash
   python -m alembic current
   ```
5. **Application deployment**
6. **Post-deployment verification**

### Rollback Procedure

```bash
# Check current revision
python -m alembic current

# Rollback to previous revision
python -m alembic downgrade -1

# Rollback to specific revision
python -m alembic downgrade 002

# Emergency rollback to base (data loss warning!)
python -m alembic downgrade base
```

## Troubleshooting

### Common Issues

#### Migration Conflicts
```bash
# Multiple heads detected
python -m alembic merge -m "merge message"
```

#### Schema Drift
```bash
# Compare database to models
python -m alembic check
```

#### Failed Migration
```bash
# Mark revision as applied (dangerous!)
python -m alembic stamp head

# Manual schema fix then stamp
# Fix database manually, then:
python -m alembic stamp revision_id
```

### Performance Issues

#### Large Table Migrations
- Use batch operations for large datasets
- Consider maintenance windows
- Monitor lock duration
- Implement progress tracking

```python
def upgrade():
    # For large tables, process in batches
    connection = op.get_bind()
    
    batch_size = 10000
    offset = 0
    
    while True:
        result = connection.execute(text(f"""
            UPDATE large_table 
            SET new_column = calculated_value 
            WHERE new_column IS NULL 
            LIMIT {batch_size}
        """))
        
        if result.rowcount == 0:
            break
            
        offset += batch_size
        print(f"Processed {offset} rows...")
```

#### Index Creation
```python
def upgrade():
    # Create index concurrently (PostgreSQL)
    op.create_index(
        'ix_table_column', 
        'table_name', 
        ['column'], 
        postgresql_concurrently=True
    )
```

### Error Recovery

#### Partial Migration Failure
1. Identify failed operation
2. Fix underlying issue
3. Resume or restart migration
4. Verify data integrity

#### Data Corruption
1. Stop application
2. Restore from backup
3. Investigate root cause
4. Fix migration script
5. Retry deployment

## Migration History

### Current Migrations

| Revision | Description | Date | Notes |
|----------|-------------|------|-------|
| 003 | Add job_executions table | 2025-06-25 | Scheduler functionality |

### Planned Migrations

Future migrations should be tracked in GitHub issues with the `migration` label.

## References

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Migration Best Practices](https://www.postgresql.org/docs/current/ddl-alter.html)
- [PaidSearchNav Architecture Guide](./ARCHITECTURE.md)