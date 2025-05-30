import hashlib
import base64

def hash_text(plain_text):
    """Hash the given plain text using SHA-256 and encode with base64."""
    sha256_hash = hashlib.sha256(plain_text.encode()).digest()
    return base64.b64encode(sha256_hash).decode()

def verify_text(plain_text, hashed_text):
    """Verify if the plain text matches the hashed text."""
    return hash_text(plain_text) == hashed_text

if __name__ == "__main__":
    # USER PASSWORD
    user_password = "Aji Ganteng"
    # MASTER PASSWORD
    master_password = "cari sendiri"

    # Hash passwords
    hashed_user = hash_text(user_password)
    hashed_master = hash_text(master_password)

    print("Hashed USER PASSWORD:", hashed_user)
    print("Hashed MASTER PASSWORD:", hashed_master)

    # Verify to check
    print("Verify USER PASSWORD:", verify_text(user_password, hashed_user))
    print("Verify MASTER PASSWORD:", verify_text(master_password, hashed_master))

    # Hashed USER PASSWORD: YUYE71a2R+LyX/VpwnvCnlbudeVgPN4l2jesHh6vufg=
    # Hashed MASTER PASSWORD: pQlPu3HwWxXXHhLC5laOV4AgwbbqHH+aJlgUdpisM1o=
    # Verify USER PASSWORD: True
    # Verify MASTER PASSWORD: True