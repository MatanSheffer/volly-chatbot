"""
Phone number utilities for standardizing and formatting phone numbers
across different contexts (WhatsApp API, database storage, display).
"""

import re


def normalize_phone_number(phone: str, country: str = "Israel") -> str:
    """
    Normalizes a phone number to international format without the '+' prefix.
    
    Args:
        phone: Phone number in any format (with or without country code)
        country: Country name to apply country-specific rules
        
    Returns:
        Normalized phone number in international format (e.g., "972501234567")
        
    Examples:
        >>> normalize_phone_number("050-123-4567", "Israel")
        "972501234567"
        >>> normalize_phone_number("972501234567", "Israel")
        "972501234567"
        >>> normalize_phone_number("+972 50 123 4567", "Israel")
        "972501234567"
    """
    # Remove all non-digit characters
    clean_phone = re.sub(r'\D', '', phone)
    
    if country.lower() == "israel":
        # If starts with 0, replace with 972
        if clean_phone.startswith("0"):
            return "972" + clean_phone[1:]
        # If already starts with 972, return as is
        if clean_phone.startswith("972"):
            return clean_phone
        # If it's just digits without country code, assume Israel
        if len(clean_phone) == 9 or len(clean_phone) == 10:
            if clean_phone.startswith("5"):  # Mobile number
                return "972" + clean_phone
    
    # Default: return cleaned number as-is
    return clean_phone


def format_for_whatsapp(phone: str) -> str:
    """
    Formats a phone number for WhatsApp API (international format without '+').
    
    Args:
        phone: Phone number in any format
        
    Returns:
        Phone number ready for WhatsApp API
        
    Example:
        >>> format_for_whatsapp("050-123-4567")
        "972501234567"
    """
    # WhatsApp uses the same format as our normalized format
    return normalize_phone_number(phone)


def format_for_display(phone: str, country: str = "Israel") -> str:
    """
    Formats a phone number for human-readable display.
    
    Args:
        phone: Phone number in any format
        country: Country for formatting rules
        
    Returns:
        Human-readable phone number
        
    Example:
        >>> format_for_display("972501234567", "Israel")
        "050-123-4567"
    """
    clean_phone = re.sub(r'\D', '', phone)
    
    if country.lower() == "israel":
        # Remove 972 prefix if present
        if clean_phone.startswith("972"):
            clean_phone = "0" + clean_phone[3:]
        
        # Format as XXX-XXX-XXXX
        if len(clean_phone) == 10:
            return f"{clean_phone[0:3]}-{clean_phone[3:6]}-{clean_phone[6:]}"
        elif len(clean_phone) == 9:
            return f"{clean_phone[0:2]}-{clean_phone[2:5]}-{clean_phone[5:]}"
    
    # Default: return with dashes every 3 digits
    return "-".join([clean_phone[i:i+3] for i in range(0, len(clean_phone), 3)])


def are_phones_equivalent(phone1: str, phone2: str, country: str = "Israel") -> bool:
    """
    Checks if two phone numbers are equivalent after normalization.
    
    Args:
        phone1: First phone number
        phone2: Second phone number
        country: Country for normalization rules
        
    Returns:
        True if the phones are equivalent, False otherwise
        
    Example:
        >>> are_phones_equivalent("050-123-4567", "972501234567")
        True
    """
    return normalize_phone_number(phone1, country) == normalize_phone_number(phone2, country)
