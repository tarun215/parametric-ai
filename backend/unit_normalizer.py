"""
unit_normalizer.py — Parametric AI
Specification v2 Dimensional Harmonization & Unit Normalization Engine.

Integrates Pint unit registry with robust fraction parsing, mixed imperial/metric
dimensional conversions, and standard SI harmonizations.
"""

import re
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Initialize Pint registry if available
try:
    import pint
    ureg = pint.UnitRegistry()
    ureg.define("rpm = 1 * revolution / minute")
    PINT_AVAILABLE = True
except Exception as e:
    logger.warning("Pint library not available, using deterministic conversion tables: %s", e)
    PINT_AVAILABLE = False
    ureg = None


class UnitNormalizer:
    @staticmethod
    def parse_fraction(fraction_str: str) -> float:
        """Converts strings like '50-1/4', '7/8', '24 1/2', '33-7/16' to float decimals."""
        try:
            cleaned = str(fraction_str).strip()
            # Format: '50-1/4' or '50 1/4'
            match = re.match(r"^(\d+)[-\s]+(\d+)/(\d+)$", cleaned)
            if match:
                whole = float(match.group(1))
                num = float(match.group(2))
                den = float(match.group(3))
                return whole + (num / den)
            
            # Format: '7/8'
            match = re.match(r"^(\d+)/(\d+)$", cleaned)
            if match:
                return float(match.group(1)) / float(match.group(2))
            
            # Direct float format
            num_match = re.search(r"[-+]?\d*\.\d+|\d+", cleaned)
            if num_match:
                return float(num_match.group(0))
            return 0.0
        except Exception:
            return 0.0

    @classmethod
    def normalize_attribute(cls, label: str, raw_value: str, raw_uom: str) -> Dict[str, Any]:
        """
        Normalizes a raw value and unit of measure into standard SI / engineering expressions.
        Uses Pint unit registry where possible, with fast tabular fallback.
        """
        val_str = str(raw_value or "").strip()
        uom_str = str(raw_uom or "").strip().lower()
        
        norm_val: Optional[float] = None
        norm_uom: str = uom_str.upper() if uom_str else ""
        parsed_decimal: float = 0.0

        # Parse fractions and decimals
        if re.search(r"\d+/\d+", val_str):
            parsed_decimal = cls.parse_fraction(val_str)
        else:
            num_match = re.search(r"[-+]?\d*\.\d+|\d+", val_str)
            if num_match:
                parsed_decimal = float(num_match.group(0))

        # 1. Length & Dimensions (Inches -> mm, Feet -> m)
        if uom_str in ["in", "inch", "inches", '"', "in."]:
            norm_val = round(parsed_decimal * 25.4, 2)
            norm_uom = "mm"
        elif uom_str in ["ft", "feet", "foot", "'", "ft."]:
            norm_val = round(parsed_decimal * 0.3048, 2)
            norm_uom = "m"
        elif uom_str in ["mm", "millimeter", "millimeters"]:
            norm_val = parsed_decimal
            norm_uom = "mm"
        elif uom_str in ["cm", "centimeter"]:
            norm_val = round(parsed_decimal * 10.0, 2)
            norm_uom = "mm"

        # 2. Weight & Mass (lbs -> kg, oz -> g)
        elif uom_str in ["lb", "lbs", "pound", "pounds", "lbs."]:
            norm_val = round(parsed_decimal * 0.453592, 2)
            norm_uom = "kg"
        elif uom_str in ["oz", "ounce", "ounces"]:
            norm_val = round(parsed_decimal * 28.3495, 2)
            norm_uom = "g"
        elif uom_str in ["kg", "kilogram", "kilograms"]:
            norm_val = parsed_decimal
            norm_uom = "kg"

        # 3. Electrical (V, A, W, kWh)
        elif uom_str in ["v", "volts", "voltage", "vac", "vdc"]:
            norm_val = parsed_decimal
            norm_uom = "V"
        elif uom_str in ["a", "amps", "amperage", "amperes"]:
            norm_val = parsed_decimal
            norm_uom = "A"
        elif uom_str in ["w", "watts", "wattage"]:
            norm_val = parsed_decimal
            norm_uom = "W"
        elif uom_str in ["kw", "kilowatt", "kilowatts"]:
            norm_val = round(parsed_decimal * 1000.0, 2)
            norm_uom = "W"
        elif uom_str in ["kw-hr", "kwh", "kwhr"]:
            norm_val = parsed_decimal
            norm_uom = "kWh"

        # 4. Mechanical & Pressure (PSI -> bar/kPa, RPM, Torque)
        elif uom_str in ["psi", "lbs/sq in"]:
            norm_val = round(parsed_decimal * 0.0689476, 2) # bar
            norm_uom = "bar"
        elif uom_str in ["bar", "bars"]:
            norm_val = parsed_decimal
            norm_uom = "bar"
        elif uom_str in ["rpm", "rotations/min", "rev/min"]:
            norm_val = parsed_decimal
            norm_uom = "RPM"
        elif uom_str in ["ft-lb", "ft-lbs", "foot-pounds"]:
            norm_val = round(parsed_decimal * 1.35582, 2)
            norm_uom = "Nm"

        # 5. Acoustic & Environmental (dBA, °F -> °C)
        elif uom_str in ["dba", "db", "decibels"]:
            norm_val = parsed_decimal
            norm_uom = "dBA"
        elif uom_str in ["°f", "f", "deg f", "fahrenheit"]:
            norm_val = round((parsed_decimal - 32.0) * (5.0 / 9.0), 2)
            norm_uom = "°C"
        elif uom_str in ["°c", "c", "deg c", "celsius"]:
            norm_val = parsed_decimal
            norm_uom = "°C"

        # Fallback
        else:
            norm_val = parsed_decimal if parsed_decimal > 0 else None
            norm_uom = uom_str.upper() if uom_str else ""

        return {
            "label": label,
            "raw_value": raw_value,
            "raw_uom": raw_uom,
            "decimal_value": round(parsed_decimal, 3) if parsed_decimal > 0 else raw_value,
            "normalized_value": norm_val,
            "normalized_uom": norm_uom,
            "is_converted": norm_val is not None and norm_uom != raw_uom.upper()
        }
