import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "utils"))

from email_client import EmailClient

mailer = EmailClient()
