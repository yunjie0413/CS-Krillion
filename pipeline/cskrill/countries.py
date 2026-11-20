"""ISO 3166-1 alpha-2 codes -> English names.

Liquipedia stores tournament locations with country codes ("de"), but player
nationalities as names ("Germany"). Event-host prompts need names, so codes are
mapped here. `cskrill profile` lists any code missing from this table.
"""

COUNTRY_NAMES = {
    "ad": "Andorra", "ae": "United Arab Emirates", "al": "Albania", "am": "Armenia",
    "ar": "Argentina", "at": "Austria", "au": "Australia", "az": "Azerbaijan",
    "ba": "Bosnia and Herzegovina", "bd": "Bangladesh", "be": "Belgium", "bg": "Bulgaria",
    "bh": "Bahrain", "bo": "Bolivia", "br": "Brazil", "by": "Belarus", "ca": "Canada",
    "ch": "Switzerland", "cl": "Chile", "cn": "China", "co": "Colombia", "cr": "Costa Rica",
    "cy": "Cyprus", "cz": "Czech Republic", "de": "Germany", "dk": "Denmark",
    "do": "Dominican Republic", "dz": "Algeria", "ec": "Ecuador", "ee": "Estonia", "eg": "Egypt",
    "es": "Spain", "fi": "Finland", "fr": "France", "gb": "United Kingdom", "uk": "United Kingdom",
    "ge": "Georgia", "gr": "Greece", "gt": "Guatemala", "hk": "Hong Kong", "hr": "Croatia",
    "hu": "Hungary", "id": "Indonesia", "ie": "Ireland", "il": "Israel", "in": "India",
    "iq": "Iraq", "ir": "Iran", "is": "Iceland", "it": "Italy", "jo": "Jordan", "jp": "Japan",
    "kg": "Kyrgyzstan", "kr": "South Korea", "kw": "Kuwait", "kz": "Kazakhstan", "lb": "Lebanon",
    "li": "Liechtenstein", "lk": "Sri Lanka", "lt": "Lithuania", "lu": "Luxembourg", "lv": "Latvia",
    "ma": "Morocco", "mc": "Monaco", "md": "Moldova", "me": "Montenegro", "mk": "North Macedonia",
    "mn": "Mongolia", "mo": "Macau", "mt": "Malta", "mx": "Mexico", "my": "Malaysia",
    "ng": "Nigeria", "nl": "Netherlands", "no": "Norway", "np": "Nepal", "nz": "New Zealand",
    "om": "Oman", "pa": "Panama", "pe": "Peru", "ph": "Philippines", "pk": "Pakistan",
    "pl": "Poland", "pr": "Puerto Rico", "pt": "Portugal", "py": "Paraguay", "qa": "Qatar",
    "ro": "Romania", "rs": "Serbia", "ru": "Russia", "sa": "Saudi Arabia", "se": "Sweden",
    "sg": "Singapore", "si": "Slovenia", "sk": "Slovakia", "th": "Thailand", "tn": "Tunisia",
    "tr": "Turkey", "tw": "Taiwan", "ua": "Ukraine", "us": "United States", "uy": "Uruguay",
    "uz": "Uzbekistan", "ve": "Venezuela", "vn": "Vietnam", "xk": "Kosovo", "za": "South Africa",
}


def country_name(value: str) -> str:
    """'de' / 'DE' -> 'Germany'; full names and unknown codes pass through."""
    v = value.strip()
    if len(v) == 2 and v.isalpha():
        return COUNTRY_NAMES.get(v.lower(), v.upper())
    return v


def is_unmapped_code(value: str) -> bool:
    v = value.strip()
    return len(v) == 2 and v.isalpha() and v.lower() not in COUNTRY_NAMES
