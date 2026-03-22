import struct 
from typing import Union, List, Any 
import numpy as np


class SSVHash:
    """
    Simplified custom hash for simulation state data.
    Uses:
    1. Polynomial rolling hash
    2. A small XOR-based mixing step
    """

    MODULUS = 2**61 - 1
    BASE = 31

    @staticmethod
    def hash_string(data: str) -> str:
        if not isinstance(data, str):
            raise TypeError("Input must be a string")

        hash_val = 0

        # Polynomial rolling hash, one character at a time
        for char in data:
            hash_val = (hash_val * SSVHash.BASE + ord(char)) % SSVHash.MODULUS

        # Simple XOR mixing step
        hash_val ^= (hash_val >> 16)

        # Return as uppercase hexadecimal
        return f"{hash_val:016X}"

    @staticmethod
    def hash_ssv_data(time: float, ssv: np.ndarray,
                      elevator: float = 0.0,
                      thrust: float = 0.0,
                      stall: bool = False):
        """
        Hash one simulation timestep.
        """

        ssv_str = ""
        for value in ssv.flatten():
            ssv_str += f"{value:.6f},"
        ssv_str = ssv_str.rstrip(",")
        
        data_str = f"{time:.6f},{ssv_str},{elevator:.6f},{thrust:.1f},{stall}"

        return SSVHash.hash_string(data_str)

    @staticmethod
    def validate_csv_file(csv_path: str, expected_hash: str) -> bool:
        """
        Check whether a CSV file still matches a stored hash.
        """
        try:
            with open(csv_path, "r", encoding="utf-8") as file:
                content = file.read()

            computed_hash = SSVHash.hash_string(content)
            return computed_hash == expected_hash

        except Exception:
            return False


