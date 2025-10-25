#!/usr/bin/env python3
"""
Database Connection and Schema Creation Tests
Tests for PostgreSQL migration validation
"""

import os
import sys
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

# Add the current directory to Python path to import main
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import Base, Country, Meta, POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_URL


class TestDatabaseConnection:
    """Test PostgreSQL database connection and configuration"""
    
    def test_postgresql_environment_variables(self):
        """Test that PostgreSQL environment variables are properly configured"""
        assert POSTGRES_HOST is not None, "POSTGRES_HOST should be configured"
        assert POSTGRES_PORT is not None, "POSTGRES_PORT should be configured"
        assert POSTGRES_DB is not None, "POSTGRES_DB should be configured"
        assert POSTGRES_USER is not None, "POSTGRES_USER should be configured"
        assert POSTGRES_PASSWORD is not None, "POSTGRES_PASSWORD should be configured"
        
        print(f"PostgreSQL Configuration:")
        print(f"  Host: {POSTGRES_HOST}")
        print(f"  Port: {POSTGRES_PORT}")
        print(f"  Database: {POSTGRES_DB}")
        print(f"  User: {POSTGRES_USER}")
        print(f"  Password: {'*' * len(POSTGRES_PASSWORD) if POSTGRES_PASSWORD else 'None'}")
    
    def test_database_url_format(self):
        """Test that DATABASE_URL is properly formatted for PostgreSQL"""
        assert DATABASE_URL.startswith("postgresql+psycopg2://"), f"DATABASE_URL should use PostgreSQL format, got: {DATABASE_URL}"
        assert POSTGRES_HOST in DATABASE_URL, "DATABASE_URL should contain the host"
        assert POSTGRES_PORT in DATABASE_URL, "DATABASE_URL should contain the port"
        assert POSTGRES_DB in DATABASE_URL, "DATABASE_URL should contain the database name"
        assert POSTGRES_USER in DATABASE_URL, "DATABASE_URL should contain the username"
        
        print(f"Database URL: {DATABASE_URL}")
    
    def test_database_connection(self):
        """Test that we can successfully connect to PostgreSQL"""
        try:
            # Create engine with PostgreSQL-specific settings
            engine = create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                future=True,
                pool_size=5,
                max_overflow=10,
                pool_timeout=30,
                pool_recycle=3600
            )
            
            # Test connection
            with engine.connect() as connection:
                result = connection.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                assert "PostgreSQL" in version, f"Expected PostgreSQL, got: {version}"
                print(f"Successfully connected to: {version}")
                
        except SQLAlchemyError as e:
            pytest.fail(f"Failed to connect to PostgreSQL database: {str(e)}")
    
    def test_database_permissions(self):
        """Test that the database user has necessary permissions"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            
            with engine.connect() as connection:
                # Test CREATE permission by creating a temporary table
                connection.execute(text("CREATE TEMPORARY TABLE test_permissions (id INTEGER)"))
                
                # Test INSERT permission
                connection.execute(text("INSERT INTO test_permissions (id) VALUES (1)"))
                
                # Test SELECT permission
                result = connection.execute(text("SELECT id FROM test_permissions"))
                assert result.fetchone()[0] == 1
                
                # Test DELETE permission
                connection.execute(text("DELETE FROM test_permissions WHERE id = 1"))
                
                print("Database user has all necessary permissions (CREATE, INSERT, SELECT, DELETE)")
                
        except SQLAlchemyError as e:
            pytest.fail(f"Database user lacks necessary permissions: {str(e)}")


class TestSchemaCreation:
    """Test SQLAlchemy schema creation with PostgreSQL"""
    
    def test_schema_creation(self):
        """Test that all tables are created correctly in PostgreSQL"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            
            # Drop existing tables to test fresh creation
            Base.metadata.drop_all(bind=engine)
            
            # Create all tables
            Base.metadata.create_all(bind=engine)
            
            # Verify tables exist
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            expected_tables = ['countries', 'meta']
            for table in expected_tables:
                assert table in tables, f"Table '{table}' was not created"
            
            print(f"Successfully created tables: {tables}")
            
        except SQLAlchemyError as e:
            pytest.fail(f"Failed to create database schema: {str(e)}")
    
    def test_country_table_structure(self):
        """Test that the Country table has the correct structure for PostgreSQL"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            inspector = inspect(engine)
            
            # Get column information for countries table
            columns = inspector.get_columns('countries')
            column_names = [col['name'] for col in columns]
            
            expected_columns = [
                'id', 'name', 'capital', 'region', 'population', 
                'currency_code', 'exchange_rate', 'estimated_gdp', 
                'flag_url', 'last_refreshed_at'
            ]
            
            for col in expected_columns:
                assert col in column_names, f"Column '{col}' missing from countries table"
            
            # Check specific column properties
            column_dict = {col['name']: col for col in columns}
            
            # Check primary key
            assert column_dict['id']['primary_key'] == 1, "id should be primary key"
            
            # Check nullable constraints
            assert column_dict['name']['nullable'] == False, "name should be NOT NULL"
            assert column_dict['population']['nullable'] == False, "population should be NOT NULL"
            
            # Check indexes
            indexes = inspector.get_indexes('countries')
            index_columns = []
            for idx in indexes:
                index_columns.extend(idx['column_names'])
            
            assert 'id' in index_columns, "id should be indexed"
            assert 'name' in index_columns, "name should be indexed"
            
            print("Country table structure is correct for PostgreSQL")
            
        except SQLAlchemyError as e:
            pytest.fail(f"Failed to verify country table structure: {str(e)}")
    
    def test_meta_table_structure(self):
        """Test that the Meta table has the correct structure for PostgreSQL"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            inspector = inspect(engine)
            
            # Get column information for meta table
            columns = inspector.get_columns('meta')
            column_names = [col['name'] for col in columns]
            
            expected_columns = ['id', 'key', 'value']
            
            for col in expected_columns:
                assert col in column_names, f"Column '{col}' missing from meta table"
            
            # Check column properties
            column_dict = {col['name']: col for col in columns}
            
            # Check primary key
            assert column_dict['id']['primary_key'] == 1, "id should be primary key"
            
            # Check nullable constraints
            assert column_dict['key']['nullable'] == False, "key should be NOT NULL"
            
            print("Meta table structure is correct for PostgreSQL")
            
        except SQLAlchemyError as e:
            pytest.fail(f"Failed to verify meta table structure: {str(e)}")


class TestSQLAlchemyModels:
    """Test that existing SQLAlchemy models work without modification"""
    
    def test_country_model_operations(self):
        """Test basic CRUD operations with Country model"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            
            session = SessionLocal()
            
            try:
                # Test CREATE
                test_country = Country(
                    name="Test Country",
                    capital="Test Capital",
                    region="Test Region",
                    population=1000000,
                    currency_code="TST",
                    exchange_rate=1.5,
                    estimated_gdp=1500000000.0,
                    flag_url="https://example.com/flag.png",
                    last_refreshed_at=datetime.now(timezone.utc)
                )
                session.add(test_country)
                session.commit()
                
                # Test READ
                retrieved = session.query(Country).filter(Country.name == "Test Country").first()
                assert retrieved is not None, "Failed to retrieve created country"
                assert retrieved.name == "Test Country"
                assert retrieved.population == 1000000
                assert retrieved.currency_code == "TST"
                
                # Test UPDATE
                retrieved.population = 2000000
                session.commit()
                
                updated = session.query(Country).filter(Country.name == "Test Country").first()
                assert updated.population == 2000000, "Failed to update country"
                
                # Test DELETE
                session.delete(updated)
                session.commit()
                
                deleted = session.query(Country).filter(Country.name == "Test Country").first()
                assert deleted is None, "Failed to delete country"
                
                print("Country model CRUD operations work correctly with PostgreSQL")
                
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            pytest.fail(f"Country model operations failed: {str(e)}")
    
    def test_meta_model_operations(self):
        """Test basic operations with Meta model"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            
            session = SessionLocal()
            
            try:
                # Test CREATE
                test_meta = Meta(key="test_key", value="test_value")
                session.add(test_meta)
                session.commit()
                
                # Test READ
                retrieved = session.query(Meta).filter(Meta.key == "test_key").first()
                assert retrieved is not None, "Failed to retrieve created meta"
                assert retrieved.value == "test_value"
                
                # Test UPDATE
                retrieved.value = "updated_value"
                session.commit()
                
                updated = session.query(Meta).filter(Meta.key == "test_key").first()
                assert updated.value == "updated_value", "Failed to update meta"
                
                # Test DELETE
                session.delete(updated)
                session.commit()
                
                deleted = session.query(Meta).filter(Meta.key == "test_key").first()
                assert deleted is None, "Failed to delete meta"
                
                print("Meta model CRUD operations work correctly with PostgreSQL")
                
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            pytest.fail(f"Meta model operations failed: {str(e)}")
    
    def test_postgresql_specific_features(self):
        """Test PostgreSQL-specific features and data types"""
        try:
            engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
            SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
            
            session = SessionLocal()
            
            try:
                # Test timezone-aware datetime
                utc_time = datetime.now(timezone.utc)
                test_country = Country(
                    name="Timezone Test Country",
                    population=1000000,
                    last_refreshed_at=utc_time
                )
                session.add(test_country)
                session.commit()
                
                # Retrieve and verify timezone handling
                retrieved = session.query(Country).filter(Country.name == "Timezone Test Country").first()
                assert retrieved.last_refreshed_at is not None
                assert retrieved.last_refreshed_at.tzinfo is not None, "Timezone information should be preserved"
                
                # Test large text fields (PostgreSQL TEXT type)
                large_text = "x" * 10000  # 10KB text
                retrieved.flag_url = large_text
                session.commit()
                
                updated = session.query(Country).filter(Country.name == "Timezone Test Country").first()
                assert len(updated.flag_url) == 10000, "Large text should be stored correctly"
                
                # Cleanup
                session.delete(updated)
                session.commit()
                
                print("PostgreSQL-specific features work correctly")
                
            finally:
                session.close()
                
        except SQLAlchemyError as e:
            pytest.fail(f"PostgreSQL-specific features test failed: {str(e)}")


if __name__ == "__main__":
    print("Running Database Connection and Schema Creation Tests...")
    print("=" * 60)
    
    # Run tests manually for immediate feedback
    test_conn = TestDatabaseConnection()
    test_schema = TestSchemaCreation()
    test_models = TestSQLAlchemyModels()
    
    try:
        print("\n1. Testing PostgreSQL Environment Variables...")
        test_conn.test_postgresql_environment_variables()
        
        print("\n2. Testing Database URL Format...")
        test_conn.test_database_url_format()
        
        print("\n3. Testing Database Connection...")
        test_conn.test_database_connection()
        
        print("\n4. Testing Database Permissions...")
        test_conn.test_database_permissions()
        
        print("\n5. Testing Schema Creation...")
        test_schema.test_schema_creation()
        
        print("\n6. Testing Country Table Structure...")
        test_schema.test_country_table_structure()
        
        print("\n7. Testing Meta Table Structure...")
        test_schema.test_meta_table_structure()
        
        print("\n8. Testing Country Model Operations...")
        test_models.test_country_model_operations()
        
        print("\n9. Testing Meta Model Operations...")
        test_models.test_meta_model_operations()
        
        print("\n10. Testing PostgreSQL-Specific Features...")
        test_models.test_postgresql_specific_features()
        
        print("\n" + "=" * 60)
        print("✅ All database connection and schema creation tests passed!")
        print("PostgreSQL migration validation successful.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        sys.exit(1)