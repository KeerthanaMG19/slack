#!/bin/bash
# Django Slack Bot - Migration Script

echo "📦 Running Django migrations..."
/Library/Frameworks/Python.framework/Versions/3.13/bin/python3 manage.py migrate
echo "✅ Migrations completed!" 