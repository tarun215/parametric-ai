"""
ForgeSpec AI - Unit Normalizer & Dimensional Harmonization Engine
Parses fractions, mixed imperial expressions, and converts to standardized metric/SI metrics.
"""

import re
from typing import Dict, Any, Optional, Tuple

class UnitNormalizer:
    @staticmethod
    def parse_fraction(fraction_str: str) -> float:
        """Converts strings like '50-1/4', '7/8', '24 1/2' to floats."""
        try:
            fraction_str = fraction_str.strip()
            # Format: '50-1/4' or '50 1/4'
            match = re.match(r'^(\d+)[-\s]+(\d+)/(\d+)$', fraction_str)
            if match:
                whole = float(match.group(1))
                num = float(match.group(2))
                den = float(match.group(3))
                return whole + (num / den)
            
            # Format: '7/8'
            match = re.match(r'^(\d+)/(\d+)$', fraction_str)
            if match:
                return float(match.group(1)) / float(match.group(2))
            
            return float(fraction_str)
        except Exception:
            return 0.0

    @staticmethod
    def normalize_attribute(label: str, raw_value: str, raw_uom: str) -> Dict[str, Any]:
        """Normalizes a raw value and unit of measure into standard metric & decimal expressions."""
        val_str = str(raw_value).strip()
        uom_str = str(raw_uom).strip().lower()
        
        # Default fallback
        norm_val: Optional[float] = None
        norm_uom: str = uom_str.upper() if uom_str else "N/A"
        parsed_decimal: float = 0.0

        # Check for fractional length (e.g. 50-1/4 or 7/8 or 0.045)
        if re.search(r'\d+/\d+', val_str):
            parsed_decimal = UnitNormalizer.parse_fraction(val_str)
        else:
            # Extract first float/int from string if possible
            num_match = re.search(r'[-+]?\d*\.\d+|\d+', val_str)
            if num_match:
                parsed_decimal = float(num_match.group(0))

        # Perform conversions based on UOM
        if uom_str in ["in", "inch", "inches", '"']:
            norm_val = round(parsed_decimal * 25.4, 2)  # mm
            norm_uom = "mm"
        elif uom_str in ["ft", "feet", "foot", "'"]:
            norm_val = round(parsed_decimal * 0.3048, 2)  # meters
            norm_uom = "m"
        elif uom_str in ["lb", "lbs", "pound", "pounds"]:
            norm_val = round(parsed_decimal * 0.453592, 2)  # kg
            norm_uom = "kg"
        elif uom_str in ["v", "volts", "voltage"]:
            norm_val = parsed_decimal
            norm_uom = "V"
        elif uom_str in ["a", "amps", "amperage"]:
            norm_val = parsed_decimal
            norm_uom = "A"
        elif uom_str in ["dba", "db"]:
            norm_val = parsed_decimal
            norm_uom = "dBA"
        elif uom_str in ["kw-hr", "kwh"]:
            norm_val = parsed_decimal
            norm_uom = "kWh"
        elif uom_str in ["rpm"]:
            norm_val = parsed_decimal
            norm_uom = "RPM"
        else:
            norm_val = parsed_decimal if parsed_decimal > 0 else None
            norm_uom = uom_str.upper() if uom_str else "N/A"

        return {
            "label": label,
            "raw_value": raw_value,
            "raw_uom": raw_uom,
            "decimal_value": round(parsed_decimal, 3) if parsed_decimal > 0 else raw_value,
            "normalized_value": norm_val,
            "normalized_uom": norm_uom,
            "is_converted": norm_val is not None and norm_uom != raw_uom.upper()
        }
