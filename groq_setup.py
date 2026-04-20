"""
Setup script for Groq API (FREE)
"""

import os
from pathlib import Path

def setup_groq():
    print("\n" + "="*60)
    print("🚀 Groq API Setup (FREE - No Credit Card Required)")
    print("="*60 + "\n")
    
    print("Step 1: Get your FREE API key")
    print("-" * 60)
    print("1. Visit: https://console.groq.com/keys")
    print("2. Sign up with email (no credit card needed)")
    print("3. Click 'Create API Key'")
    print("4. Copy your key")
    print()
    
    api_key = input("Paste your Groq API key here: ").strip()
    
    if not api_key:
        print("❌ No API key provided. Exiting...")
        return
    
    # Create .env file
    env_file = Path(".env")
    
    if env_file.exists():
        # Update existing file
        with open(env_file, 'r') as f:
            lines = f.readlines()
        
        # Replace or add GROQ_API_KEY
        updated = False
        for i, line in enumerate(lines):
            if line.startswith('GROQ_API_KEY'):
                lines[i] = f'GROQ_API_KEY={api_key}\n'
                updated = True
                break
        
        if not updated:
            lines.append(f'\nGROQ_API_KEY={api_key}\n')
        
        with open(env_file, 'w') as f:
            f.writelines(lines)
    else:
        # Create new file
        with open(env_file, 'w') as f:
            f.write(f"# Groq API Key - FREE, no credit card required\n")
            f.write(f"# Get yours at: https://console.groq.com/keys\n")
            f.write(f"GROQ_API_KEY={api_key}\n")
    
    print("\n✅ API key saved to .env file")
    print("\nStep 2: Test the setup")
    print("-" * 60)
    print("Run: python test_ai.py")
    print()
    print("="*60)
    print("✅ Setup Complete! You're ready to use AI-powered analysis")
    print("="*60 + "\n")

if __name__ == "__main__":
    setup_groq()