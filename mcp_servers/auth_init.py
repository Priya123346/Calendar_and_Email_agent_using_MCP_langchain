from auth import get_gmail_creds

print("Running first-time Gmail authentication...")
get_gmail_creds()
print("✅ Authentication complete. token.json created.")