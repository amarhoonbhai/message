import sys
import os
import re

# Add the project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from worker.commands import parse_group_input

def test_parsing():
    test_cases = [
        # Current supported
        ("@mygroup", "@mygroup"),
        ("mygroup", "@mygroup"),
        ("https://t.me/mygroup", "mygroup"),
        ("t.me/mygroup", "mygroup"),
        ("https://telegram.me/mygroup", "mygroup"),
        ("https://t.me/joinchat/AbCPQR123", "https://t.me/joinchat/AbCPQR123"),
        
        # New formats to support
        ("https://t.me/+AbCPQR123", "https://t.me/+AbCPQR123"),
        ("t.me/+AbCPQR123", "t.me/+AbCPQR123"),
        ("https://telegram.dog/mygroup", "mygroup"),
        ("tg://resolve?domain=mygroup", "mygroup"),
        ("tg://join?invite=AbCPQR123", "https://t.me/+AbCPQR123"),
        ("https://t.me/c/123456789/123", "123456789"), # ID extraction
    ]
    
    passed = 0
    failed = 0
    
    print(f"{'Input':<40} | {'Expected':<25} | {'Got':<25} | {'Status'}")
    print("-" * 110)
    
    for input_str, expected in test_cases:
        got = parse_group_input(input_str)
        status = "PASS" if got == expected else "FAIL"
        if got == expected:
            passed += 1
        else:
            failed += 1
        print(f"{input_str:<40} | {str(expected):<25} | {str(got):<25} | {status}")
        
    print("-" * 110)
    print(f"Total: {len(test_cases)} | Passed: {passed} | Failed: {failed}")

if __name__ == "__main__":
    test_parsing()
