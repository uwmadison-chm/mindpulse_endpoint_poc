"""Tests for encryption and decryption models."""

import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from mindpulse_endpoint_poc.models import EnrollmentKey, Encryptor, Decryptor, EncryptedMPFile


@pytest.fixture
def enrollment_key():
    """Create a test enrollment key."""
    return EnrollmentKey.generate_random()


@pytest.fixture
def test_data():
    """Create test data for encryption."""
    return b"This is test data for encryption and decryption!"


@pytest.fixture
def json_test_data():
    """Create JSON test data."""
    return b'{"test": "data", "value": 123, "nested": {"key": "value"}}'


def test_encryptor_decryptor_round_trip(enrollment_key, test_data):
    """Test that data can be encrypted and then decrypted back to original."""
    # Create encryptor and decryptor
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create source file
        source_file = temp_path / "source.txt"
        source_file.write_bytes(test_data)

        # Encrypt file
        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file for EncryptedMPFile
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_test_{iv.hex()}.txt"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile and decrypt
        mpfile = EncryptedMPFile.from_filename(encrypted_file)
        decrypted_data = decryptor.decrypt(mpfile)

        # Verify round-trip
        assert decrypted_data == test_data


def test_file_encryption_round_trip(enrollment_key, test_data):
    """Test file encryption and decryption round-trip."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create source file
        source_file = temp_path / "source.txt"
        source_file.write_bytes(test_data)

        # Encrypt file
        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file for EncryptedMPFile
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_test_{iv.hex()}.txt"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Verify encrypted file exists and has different content
        assert encrypted_file.exists()
        encrypted_content = encrypted_file.read_bytes()
        assert encrypted_content != test_data

        # Decrypt using EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)
        decrypted_data = decryptor.decrypt(mpfile)
        assert decrypted_data == test_data


def test_complete_workflow_with_filename_parsing(enrollment_key, json_test_data):
    """Test the complete workflow: encrypt → generate filename → parse → decrypt."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create source file
        source_file = temp_path / "test_data.json"
        source_file.write_bytes(json_test_data)

        # Encrypt file
        temp_encrypted = temp_path / "temp_encrypted"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Generate proper filename format
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        file_type = "data"
        iv_hex = iv.hex()

        proper_filename = f"{short_sha}_{timestamp.isoformat()}_{file_type}_{iv_hex}.json"
        final_encrypted_file = temp_path / proper_filename

        # Move to proper filename
        temp_encrypted.rename(final_encrypted_file)

        # Parse the filename back into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(final_encrypted_file)

        # Verify parsing worked correctly
        assert mpfile.short_id == short_sha
        assert mpfile.type == file_type
        assert mpfile.iv == iv
        assert mpfile.path == final_encrypted_file

        # Decrypt using the EncryptedMPFile
        decrypted_data = decryptor.decrypt(mpfile)

        # Verify round-trip
        assert decrypted_data == json_test_data


def test_mpfile_decryption_methods(enrollment_key, test_data):
    """Test both decryption methods on EncryptedMPFile."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create and encrypt file
        source_file = temp_path / "test.txt"
        source_file.write_bytes(test_data)

        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"12345678_{timestamp.isoformat()}_text_{iv.hex()}.txt"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)

        # Test decrypt method
        decrypted_bytes = decryptor.decrypt(mpfile)
        assert decrypted_bytes == test_data

        # Test decrypt_to_path method
        output_file = temp_path / "decrypted_output.txt"
        decryptor.decrypt_to_path(mpfile, output_file)

        assert output_file.exists()
        assert output_file.read_bytes() == test_data


def test_different_file_types(enrollment_key):
    """Test encryption/decryption with different types of data."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    test_cases = [
        (b"Simple text", "text"),
        (b'{"json": "data"}', "data"),
        (b"PNG fake image data", "image"),
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", "binary"),  # PNG header-like
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        for i, (test_data, data_type) in enumerate(test_cases):
            # Create source file
            source_file = temp_path / f"source_{i}.{data_type}"
            source_file.write_bytes(test_data)

            # Encrypt
            temp_encrypted = temp_path / f"temp_{i}"
            iv = encryptor.encrypt_file(source_file, temp_encrypted)

            # Create properly named file
            short_sha = enrollment_key.short_sha
            timestamp = datetime.now().astimezone().replace(microsecond=0)
            filename = f"{short_sha}_{timestamp.isoformat()}_{data_type}_{iv.hex()}.{data_type}"
            encrypted_file = temp_path / filename
            temp_encrypted.rename(encrypted_file)

            # Decrypt using EncryptedMPFile
            mpfile = EncryptedMPFile.from_filename(encrypted_file)
            decrypted = decryptor.decrypt(mpfile)

            # Verify
            assert decrypted == test_data, f"Round-trip failed for {data_type} data"


def test_encryption_produces_different_outputs(enrollment_key, test_data):
    """Test that encrypting the same data multiple times produces different outputs."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create source file
        source_file = temp_path / "source.txt"
        source_file.write_bytes(test_data)

        # Encrypt same data multiple times
        temp_encrypted1 = temp_path / "temp1"
        iv1 = encryptor.encrypt_file(source_file, temp_encrypted1)
        ciphertext1 = temp_encrypted1.read_bytes()

        temp_encrypted2 = temp_path / "temp2"
        iv2 = encryptor.encrypt_file(source_file, temp_encrypted2)
        ciphertext2 = temp_encrypted2.read_bytes()

        # Should produce different ciphertexts and IVs
        assert ciphertext1 != ciphertext2
        assert iv1 != iv2

        # But both should decrypt to original data
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)

        # Test first encryption
        filename1 = f"{short_sha}_{timestamp.isoformat()}_test1_{iv1.hex()}.txt"
        encrypted_file1 = temp_path / filename1
        temp_encrypted1.rename(encrypted_file1)
        mpfile1 = EncryptedMPFile.from_filename(encrypted_file1)
        decrypted1 = decryptor.decrypt(mpfile1)

        # Test second encryption
        filename2 = f"{short_sha}_{timestamp.isoformat()}_test2_{iv2.hex()}.txt"
        encrypted_file2 = temp_path / filename2
        temp_encrypted2.rename(encrypted_file2)
        mpfile2 = EncryptedMPFile.from_filename(encrypted_file2)
        decrypted2 = decryptor.decrypt(mpfile2)

        assert decrypted1 == test_data
        assert decrypted2 == test_data


def test_iv_length_and_format(enrollment_key, test_data):
    """Test that IV has correct length and can be hex encoded/decoded."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)

    ciphertext, iv = encryptor.encrypt(test_data)

    # IV should be 16 bytes (128 bits) for AES-CBC
    assert len(iv) == 16

    # Should be able to convert to hex and back
    iv_hex = iv.hex()
    assert len(iv_hex) == 32  # 16 bytes = 32 hex characters

    iv_decoded = bytes.fromhex(iv_hex)
    assert iv_decoded == iv


def test_decryptor_api_design(enrollment_key, test_data):
    """Test that the Decryptor API is designed around EncryptedMPFile objects."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create and encrypt file
        source_file = temp_path / "test.txt"
        source_file.write_bytes(test_data)

        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_text_{iv.hex()}.txt"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)

        # Main API should work with EncryptedMPFile
        decrypted_data = decryptor.decrypt(mpfile)
        assert decrypted_data == test_data


def test_memory_mapped_decryption(enrollment_key, test_data):
    """Test memory-mapped decryption (now the default behavior)."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create and encrypt file
        source_file = temp_path / "test.txt"
        source_file.write_bytes(test_data)

        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_text_{iv.hex()}.txt"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)

        # Test default decryption (now uses memory mapping)
        decrypted = decryptor.decrypt(mpfile)
        assert decrypted == test_data

        # Test decryption to file
        output_file = temp_path / "decrypted.txt"
        decryptor.decrypt_to_path(mpfile, output_file)

        assert output_file.exists()
        assert output_file.read_bytes() == test_data


def test_memory_mapped_decryption_large_data(enrollment_key):
    """Test memory-mapped decryption with larger data and different chunk sizes."""
    # Create larger test data (1MB)
    large_data = b"A" * (1024 * 1024)

    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create and encrypt large file
        source_file = temp_path / "large_test.bin"
        source_file.write_bytes(large_data)

        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_file_{iv.hex()}.bin"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)

        # Test with different chunk sizes
        for chunk_size in [1024, 8192, 64 * 1024]:
            decrypted = decryptor.decrypt(mpfile, chunk_size=chunk_size)
            assert decrypted == large_data

            # Test to-file version
            output_file = temp_path / f"decrypted_{chunk_size}.bin"
            decryptor.decrypt_to_path(mpfile, output_file, chunk_size=chunk_size)

            assert output_file.exists()
            assert output_file.read_bytes() == large_data
            output_file.unlink()  # Clean up


def test_file_info_method(enrollment_key, test_data):
    """Test the get_file_info method."""
    encryptor = Encryptor.from_enrollment_key(enrollment_key)
    decryptor = Decryptor.from_enrollment_key(enrollment_key)

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Create and encrypt file
        source_file = temp_path / "info_test.json"
        source_file.write_bytes(test_data)

        temp_encrypted = temp_path / "temp"
        iv = encryptor.encrypt_file(source_file, temp_encrypted)

        # Create properly named file
        short_sha = enrollment_key.short_sha
        timestamp = datetime.now().astimezone().replace(microsecond=0)
        filename = f"{short_sha}_{timestamp.isoformat()}_data_{iv.hex()}.json"
        encrypted_file = temp_path / filename
        temp_encrypted.rename(encrypted_file)

        # Parse into EncryptedMPFile
        mpfile = EncryptedMPFile.from_filename(encrypted_file)

        # Get file info
        info = decryptor.get_file_info(mpfile)

        # Verify info
        assert info["path"] == str(encrypted_file)
        assert info["encrypted_size"] > len(test_data)  # Should be larger due to encryption
        assert info["short_id"] == short_sha
        assert info["created_at"] == mpfile.created_at
        assert info["type"] == "data"
        assert info["iv"] == iv.hex()
        assert "estimated_decrypted_size" in info