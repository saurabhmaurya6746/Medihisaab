"""Frozen executable entrypoint for Pharmacy POS backend daemon."""

import multiprocessing
import sys
from pharmacy_daemon.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
