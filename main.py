#!/usr/bin/env python3
"""Root entry point — delegates to nano_biomni.main.

Run as:
    python main.py [options]
or, after pip install -e .:
    nano-biomni [options]
"""
from nano_biomni.main import main

if __name__ == "__main__":
    main()
