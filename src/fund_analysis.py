"""
Fund-by-fund spending analysis with AI replaceability categories for Dallas ISD.

Sections:
  A: Texas Fund Code Mapping
  B: Fund Code Re-Extraction from raw_line
  C: Refined AI Replaceability Category Taxonomy
  D: Fund-Level Analysis (profiles, pivots, summaries)
  E: Cross-Reference & Export
"""

import re
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import pandas as pd


# ============================================================================
# Section A: Texas Fund Code Mapping
# ============================================================================

TEXAS_FUND_CODES = {
    # 100-series: General Operating / Local
    '180': {
        'name': 'State/Local Special Revenue',
        'category': 'general_operating',
        'description': 'State and local special revenue programs',
    },
    '183': {
        'name': 'Career & Technology State Grant',
        'category': 'general_operating',
        'description': 'TEA career and technology education grants',
    },
    '197': {
        'name': 'Local Revenue Fund (197)',
        'category': 'general_operating',
        'description': 'Local revenue and campus activity',
    },
    '198': {
        'name': 'Local Revenue Fund (198)',
        'category': 'general_operating',
        'description': 'Local revenue and special purpose',
    },
    '199': {
        'name': 'General Fund',
        'category': 'general_operating',
        'description': 'Main district operating fund — covers payroll, instruction, administration, and general operations',
    },

    # 200-series: Federal Grants / Special Revenue
    '206': {
        'name': 'State Program Revenue (206)',
        'category': 'federal_state_grants',
        'description': 'State-funded program revenue',
    },
    '211': {
        'name': 'ESEA Title I, Part A',
        'category': 'federal_state_grants',
        'description': 'Improving basic programs for disadvantaged students',
    },
    '224': {
        'name': 'IDEA-B Formula',
        'category': 'federal_state_grants',
        'description': 'Special education formula grant under IDEA Part B',
    },
    '225': {
        'name': 'IDEA-B Preschool',
        'category': 'federal_state_grants',
        'description': 'Special education preschool grants under IDEA Part B',
    },
    '240': {
        'name': 'National School Lunch/Breakfast Program',
        'category': 'food_service',
        'description': 'Federal child nutrition and food service programs',
    },
    '244': {
        'name': 'Carl D. Perkins CTE',
        'category': 'federal_state_grants',
        'description': 'Career and technical education grants',
    },
    '255': {
        'name': 'Title II, Part A',
        'category': 'federal_state_grants',
        'description': 'Supporting effective instruction / teacher quality',
    },
    '263': {
        'name': 'Title III, Part A',
        'category': 'federal_state_grants',
        'description': 'English language acquisition and language enhancement',
    },
    '266': {
        'name': 'Migrant Education',
        'category': 'federal_state_grants',
        'description': 'Title I, Part C — Migrant education program',
    },
    '272': {
        'name': 'Federal Program Revenue (272)',
        'category': 'federal_state_grants',
        'description': 'Federal program revenue',
    },
    '278': {
        'name': 'Federal Grant (278)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },
    '279': {
        'name': 'Federal Grant (279)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },
    '280': {
        'name': 'Federal Grant (280)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },
    '281': {
        'name': 'ESSER I (CARES Act)',
        'category': 'federal_state_grants',
        'description': 'Elementary and Secondary School Emergency Relief — CARES Act',
    },
    '282': {
        'name': 'ESSER II/III (ARP)',
        'category': 'federal_state_grants',
        'description': 'Elementary and Secondary School Emergency Relief — CRRSA/ARP',
    },
    '284': {
        'name': 'Federal Grant (284)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },
    '285': {
        'name': 'Federal Grant (285)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },
    '288': {
        'name': 'Federal Grant (288)',
        'category': 'federal_state_grants',
        'description': 'Federal grant program',
    },

    # 300-series: Debt Service
    '315': {
        'name': 'Debt Service (315)',
        'category': 'debt_service',
        'description': 'Debt service fund for bond repayment',
    },
    '340': {
        'name': 'Debt Service (340)',
        'category': 'debt_service',
        'description': 'Debt service fund',
    },
    '385': {
        'name': 'Debt Service (385)',
        'category': 'debt_service',
        'description': 'Debt service fund',
    },
    '393': {
        'name': 'Debt Service (393)',
        'category': 'debt_service',
        'description': 'Debt service fund',
    },

    # 400-series: Capital / Debt
    '410': {
        'name': 'Debt Service (410)',
        'category': 'debt_service',
        'description': 'Interest and sinking fund for bond payments',
    },
    '429': {
        'name': 'Capital Projects (429)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '435': {
        'name': 'Capital Projects (435)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '458': {
        'name': 'Capital Projects (458)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '481': {
        'name': 'Capital Projects (481)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '488': {
        'name': 'Capital Projects (488)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '489': {
        'name': 'Capital Projects (489)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '492': {
        'name': 'Capital Projects (492)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },
    '493': {
        'name': 'Capital Projects (493)',
        'category': 'capital_projects',
        'description': 'Capital projects fund',
    },

    # 500-series: Food Service / Enterprise
    '528': {
        'name': 'Child Nutrition (528)',
        'category': 'food_service',
        'description': 'Child nutrition enterprise fund',
    },
    '529': {
        'name': 'Child Nutrition (529)',
        'category': 'food_service',
        'description': 'Child nutrition enterprise fund',
    },
    '551': {
        'name': 'Enterprise Fund (551)',
        'category': 'food_service',
        'description': 'District enterprise operations',
    },

    # 600-series: Capital Projects / Bond Construction
    '628': {
        'name': 'Bond Construction (628)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '629': {
        'name': 'Bond Construction (629)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '634': {
        'name': 'Bond Construction (634)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '635': {
        'name': 'Bond Construction (635)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '636': {
        'name': 'Bond Construction (636)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '637': {
        'name': 'Bond Construction (2020 Election)',
        'category': 'bond_construction',
        'description': 'Bond-funded projects from 2020 bond election',
    },
    '638': {
        'name': 'Bond Construction (638)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '640': {
        'name': 'Bond Construction (640)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '650': {
        'name': 'Bond Construction (650)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '651': {
        'name': 'Bond Construction (2015 Election)',
        'category': 'bond_construction',
        'description': 'Bond-funded projects from 2015 bond election',
    },
    '652': {
        'name': 'Bond Construction (652)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '653': {
        'name': 'Bond Construction (653)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '654': {
        'name': 'Bond Construction (654)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },
    '655': {
        'name': 'Bond Construction (655)',
        'category': 'bond_construction',
        'description': 'Bond-funded capital construction projects',
    },

    # 700-series: Trust & Agency
    '712': {
        'name': 'Student Activity Fund',
        'category': 'trust_agency',
        'description': 'Student activity and campus trust funds',
    },
    '752': {
        'name': 'Self-Insurance (752)',
        'category': 'trust_agency',
        'description': 'Self-insurance programs (health, dental)',
    },
    '753': {
        'name': 'Workers Compensation',
        'category': 'trust_agency',
        'description': 'Workers compensation self-insurance fund',
    },
    '771': {
        'name': 'Private Purpose Trust',
        'category': 'trust_agency',
        'description': 'Private purpose trust and scholarship funds',
    },

    # 900-series: Internal/Memo
    '902': {
        'name': 'Internal Service Fund',
        'category': 'internal',
        'description': 'Internal service fund for inter-departmental charges',
    },
}

# Alphanumeric fund code mappings (ESSER variants, COVID relief, etc.)
ALPHANUMERIC_FUND_CODES = {
    '21F': {'name': 'Title I Variant (21F)', 'category': 'federal_state_grants'},
    '21M': {'name': 'Title I Variant (21M)', 'category': 'federal_state_grants'},
    '21S': {'name': 'Title I Variant (21S)', 'category': 'federal_state_grants'},
    '25A': {'name': 'IDEA Variant (25A)', 'category': 'federal_state_grants'},
    '26I': {'name': 'Title III Variant (26I)', 'category': 'federal_state_grants'},
    '28A': {'name': 'ESSER/COVID Relief (28A)', 'category': 'federal_state_grants'},
    '28B': {'name': 'ESSER/COVID Relief (28B)', 'category': 'federal_state_grants'},
    '28C': {'name': 'ESSER/COVID Relief (28C)', 'category': 'federal_state_grants'},
    '28D': {'name': 'ESSER/COVID Relief (28D)', 'category': 'federal_state_grants'},
    '28F': {'name': 'ESSER/COVID Relief (28F)', 'category': 'federal_state_grants'},
    '28L': {'name': 'ESSER/COVID Relief (28L)', 'category': 'federal_state_grants'},
    '28M': {'name': 'ESSER/COVID Relief (28M)', 'category': 'federal_state_grants'},
    '28R': {'name': 'ESSER/COVID Relief (28R)', 'category': 'federal_state_grants'},
    '42B': {'name': 'Capital/ESSER Variant (42B)', 'category': 'capital_projects'},
    '42C': {'name': 'Capital/ESSER Variant (42C)', 'category': 'capital_projects'},
    '42H': {'name': 'Capital/ESSER Variant (42H)', 'category': 'capital_projects'},
    '42K': {'name': 'Capital/ESSER Variant (42K)', 'category': 'capital_projects'},
    '42L': {'name': 'Capital/ESSER Variant (42L)', 'category': 'capital_projects'},
    '48B': {'name': 'Bond/Capital Variant (48B)', 'category': 'bond_construction'},
    '48C': {'name': 'Bond/Capital Variant (48C)', 'category': 'bond_construction'},
    '48D': {'name': 'Bond/Capital Variant (48D)', 'category': 'bond_construction'},
    '49J': {'name': 'Bond/Capital Variant (49J)', 'category': 'bond_construction'},
    '49L': {'name': 'Bond/Capital Variant (49L)', 'category': 'bond_construction'},
    '49P': {'name': 'Bond/Capital Variant (49P)', 'category': 'bond_construction'},
    '49Q': {'name': 'Bond/Capital Variant (49Q)', 'category': 'bond_construction'},
}

FUND_CATEGORY_LABELS = {
    'general_operating': 'General Operating',
    'federal_state_grants': 'Federal/State Grants',
    'food_service': 'Food Service',
    'debt_service': 'Debt Service',
    'capital_projects': 'Capital Projects',
    'bond_construction': 'Bond Construction',
    'trust_agency': 'Trust & Agency',
    'internal': 'Internal Service',
}


def get_fund_info(fund_code: str) -> dict:
    """Look up fund code metadata. Returns info dict or a default for unknown codes."""
    if fund_code in TEXAS_FUND_CODES:
        return TEXAS_FUND_CODES[fund_code]
    if fund_code in ALPHANUMERIC_FUND_CODES:
        return ALPHANUMERIC_FUND_CODES[fund_code]
    return {
        'name': f'Unknown Fund ({fund_code})',
        'category': 'unknown',
        'description': f'Unrecognized fund code {fund_code}',
    }


# ============================================================================
# Section B: Fund Code Re-Extraction from raw_line
# ============================================================================

# Pre-compiled regex for check line structure
_CHECK_LINE_RE = re.compile(
    r'(\d{7,10})\s+(\d{2}/\d{2}/\d{4})\s+([\d,]+\.\d{2})'
)
# 3-digit numeric fund code followed by a signed amount
_FUND_NUMERIC_RE = re.compile(
    r'\b([1-9]\d{2})\b\s+(-?[\d,]+\.\d{2})'
)
# 2-digit + letter alphanumeric fund code followed by a signed amount
_FUND_ALPHA_RE = re.compile(
    r'\b(\d{2}[A-Z])\b\s+(-?[\d,]+\.\d{2})'
)


def extract_fund_code_from_raw_line(raw_line: str) -> Optional[str]:
    """
    Extract the 3-character fund code from a raw PDF line.

    Strategy: after the check amount, find a fund code (3-digit numeric or
    2-digit+letter) that is followed by a signed numeric amount.
    Prefers numeric codes; falls back to alphanumeric.

    Args:
        raw_line: The original text line from the PDF.

    Returns:
        Fund code string (e.g. '199', '28B') or None if not found.
    """
    if not isinstance(raw_line, str):
        return None

    check_match = _CHECK_LINE_RE.search(raw_line)
    if not check_match:
        return None

    remainder = raw_line[check_match.end(3):]

    # Try 3-digit numeric first (most common)
    fund_match = _FUND_NUMERIC_RE.search(remainder)
    if fund_match:
        return fund_match.group(1)

    # Try alphanumeric (2-digit + letter)
    fund_match = _FUND_ALPHA_RE.search(remainder)
    if fund_match:
        return fund_match.group(1)

    return None


def add_fund_codes_to_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add fund_code and fund_name columns by re-extracting from raw_line.

    Args:
        df: Transactions DataFrame with 'raw_line' column.

    Returns:
        DataFrame with added 'fund_code' and 'fund_name' columns.
    """
    df = df.copy()
    df['fund_code'] = df['raw_line'].apply(extract_fund_code_from_raw_line)
    df['fund_name'] = df['fund_code'].apply(
        lambda c: get_fund_info(c)['name'] if c else 'Unknown'
    )
    df['fund_category'] = df['fund_code'].apply(
        lambda c: get_fund_info(c)['category'] if c else 'unknown'
    )
    return df


# ============================================================================
# Section C: Refined AI Replaceability Category Taxonomy
# ============================================================================

AI_REPLACEABILITY_CATEGORIES = {
    # Software platforms (high AI replaceability potential)
    'lms_classroom': {
        'name': 'LMS & Classroom Management',
        'ai_potential': 'high',
        'description': 'Learning management systems, classroom platforms, gradebooks',
    },
    'assessment_testing': {
        'name': 'Assessment & Testing',
        'ai_potential': 'high',
        'description': 'Standardized testing, formative assessment, benchmark platforms',
    },
    'sis_data_compliance': {
        'name': 'SIS, Data & Compliance',
        'ai_potential': 'medium',
        'description': 'Student information systems, data warehouses, compliance/reporting',
    },
    'hr_erp_admin': {
        'name': 'HR, ERP & Admin Systems',
        'ai_potential': 'medium',
        'description': 'Human resources, enterprise resource planning, financial admin systems',
    },

    # Content + platform hybrids (mixed)
    'curriculum_digital': {
        'name': 'Digital Curriculum',
        'ai_potential': 'medium',
        'description': 'Full digital curriculum suites (e.g. Amplify, Great Minds Eureka)',
    },
    'adaptive_learning': {
        'name': 'Adaptive Learning Platforms',
        'ai_potential': 'medium',
        'description': 'Adaptive/personalized learning with algorithm-driven paths',
    },
    'supplemental_edtech': {
        'name': 'Supplemental EdTech',
        'ai_potential': 'high',
        'description': 'Supplemental tools, enrichment apps, classroom add-ons',
    },

    # Content only
    'textbooks_publishing': {
        'name': 'Textbooks & Publishing',
        'ai_potential': 'low',
        'description': 'Physical/digital textbooks, publisher content licensing',
    },
    'library_media': {
        'name': 'Library & Media',
        'ai_potential': 'low',
        'description': 'Library systems, media subscriptions, digital content libraries',
    },

    # Infrastructure
    'it_hardware': {
        'name': 'IT Hardware',
        'ai_potential': 'none',
        'description': 'Computers, networking equipment, devices, peripherals',
    },
    'it_software_infra': {
        'name': 'IT Software & Infrastructure',
        'ai_potential': 'low',
        'description': 'Operating systems, security software, network management, cloud',
    },
    'it_managed_services': {
        'name': 'IT Managed Services',
        'ai_potential': 'low',
        'description': 'Outsourced IT services, managed hosting, support contracts',
    },

    # Non-tech categories
    'construction_facilities': {
        'name': 'Construction & Facilities',
        'ai_potential': 'none',
        'description': 'Construction, maintenance, utilities, facilities management',
    },
    'payroll_benefits': {
        'name': 'Payroll & Benefits',
        'ai_potential': 'none',
        'description': 'Employee compensation, retirement, insurance, taxes',
    },
    'food_transportation': {
        'name': 'Food & Transportation',
        'ai_potential': 'none',
        'description': 'Food services, student transportation, fleet operations',
    },
    'professional_services': {
        'name': 'Professional Services',
        'ai_potential': 'low',
        'description': 'Consulting, legal, auditing, professional development',
    },
    'other': {
        'name': 'Other',
        'ai_potential': 'none',
        'description': 'Spending not fitting other categories',
    },
}

# Pass1 category -> AI category direct mapping for non-edtech categories
_PASS1_TO_AI_CATEGORY = {
    'payroll_benefits': 'payroll_benefits',
    'facilities_construction': 'construction_facilities',
    'food_nutrition': 'food_transportation',
    'transportation': 'food_transportation',
    'insurance_finance': 'payroll_benefits',
    'hr_professional_services': 'professional_services',
    'other': 'other',
}

# Keyword patterns for edtech sub-categorization
_EDTECH_NAME_PATTERNS = {
    'lms_classroom': [
        'canvas', 'schoology', 'google classroom', 'classlink', 'clever',
        'seesaw', 'classdojo', 'schoolmint', 'nearpod', 'pear deck',
    ],
    'assessment_testing': [
        'nwea', 'northwest evaluation', 'istation', 'renaissance learning',
        'curriculum associates', 'i-ready', 'dibels', 'aimsweb', 'star ',
        'fastbridge', 'assessment', 'testing', 'benchmark', 'mclass',
        'evaluation assoc', 'measure', 'acuity',
    ],
    'adaptive_learning': [
        'dreambox', 'khan academy', 'ixl', 'zearn', 'newsela',
        'imagine learning', 'lexia', 'achieve3000', 'achieve 3000',
        'razplus', 'raz-plus', 'learning.com', 'edgenuity',
        'study island', 'freckle',
    ],
    'curriculum_digital': [
        'amplify', 'great minds', 'eureka', 'savvas', 'mcgraw',
        'houghton mifflin', 'pearson', 'discovery education', 'studysync',
        'into reading', 'into math', 'wonders', 'open up resources',
        'kendall hunt', 'carnegie learning', 'college board',
        'curriculum', 'teks resource',
    ],
    'supplemental_edtech': [
        'brainpop', 'flocabulary', 'epic!', 'prodigy', 'kahoot',
        'quizlet', 'padlet', 'flipgrid', 'edpuzzle', 'screencastify',
        'book creator', 'tinkercad', 'code.org', 'scratch',
        'typing.com', 'learning a-z', 'learning ally',
    ],
    'textbooks_publishing': [
        'scholastic', 'textbook', 'publications', 'publishing',
        'capstone', 'national geographic', 'teacher created',
        'heinemann', 'stenhouse', 'corwin',
    ],
    'library_media': [
        'follett', 'mackin', 'library', 'overdrive', 'ebsco',
    ],
    'sis_data_compliance': [
        'powerschool', 'skyward', 'infinite campus', 'frontline',
        'eduphoria', 'student information', 'compliance',
    ],
    'hr_erp_admin': [
        'oracle', 'sap ', 'workday', 'kronos', 'munis',
        'tyler technologies',
    ],
    'it_hardware': [
        'lenovo', 'dell ', 'apple', 'cdw', 'troxell', 'hp ',
        'hewlett', 'cisco', 'chromebook', 'printer',
    ],
    'it_software_infra': [
        'microsoft', 'vmware', 'securly', 'lightspeed', 'sophos',
        'crowdstrike', 'fortinet', 'palo alto', 'splunk',
    ],
    'it_managed_services': [
        'compucom', 'managed service', 'support contract',
    ],
}

# V2 classification -> AI category mapping
_V2_CLASSIFICATION_MAP = {
    'platform': None,  # needs sub-categorization
    'curriculum_platform': 'curriculum_digital',
    'content': 'textbooks_publishing',
    'services': 'professional_services',
    'hybrid': None,  # needs sub-categorization
    'physical': 'it_hardware',
    'unknown': 'other',
}


def categorize_vendor_for_ai_analysis(
    vendor_name: str,
    pass1_category: str,
    edtech_research: Optional[dict] = None,
) -> dict:
    """
    Assign a refined AI replaceability category to a vendor.

    3-tier approach:
      1. Use v2 research classification if available and informative
      2. Direct mapping for non-edtech pass1 categories
      3. Enhanced name heuristics for edtech sub-categorization

    Args:
        vendor_name: Vendor name string.
        pass1_category: Category from pass1 (e.g. 'edtech_instructional').
        edtech_research: Optional dict from edtech_research_v2.json entry.

    Returns:
        dict with keys: ai_category, ai_category_name, confidence
    """
    vendor_lower = vendor_name.lower()

    # --- Tier 1: use v2 research if available ---
    if edtech_research:
        classification = edtech_research.get('classification', 'unknown')
        mapped = _V2_CLASSIFICATION_MAP.get(classification)
        if mapped:
            return {
                'ai_category': mapped,
                'ai_category_name': AI_REPLACEABILITY_CATEGORIES[mapped]['name'],
                'confidence': 'high',
            }
        # For 'platform' or 'hybrid', try to sub-categorize using name heuristics
        # (fall through to tier 3)

    # --- Tier 2: direct mapping for non-edtech pass1 categories ---
    if pass1_category != 'edtech_instructional' and pass1_category != 'it_infrastructure':
        ai_cat = _PASS1_TO_AI_CATEGORY.get(pass1_category, 'other')
        return {
            'ai_category': ai_cat,
            'ai_category_name': AI_REPLACEABILITY_CATEGORIES[ai_cat]['name'],
            'confidence': 'medium',
        }

    # IT infrastructure gets its own sub-categorization
    if pass1_category == 'it_infrastructure':
        for cat_key in ['it_hardware', 'it_software_infra', 'it_managed_services']:
            for pattern in _EDTECH_NAME_PATTERNS.get(cat_key, []):
                if pattern in vendor_lower:
                    return {
                        'ai_category': cat_key,
                        'ai_category_name': AI_REPLACEABILITY_CATEGORIES[cat_key]['name'],
                        'confidence': 'medium',
                    }
        return {
            'ai_category': 'it_hardware',
            'ai_category_name': AI_REPLACEABILITY_CATEGORIES['it_hardware']['name'],
            'confidence': 'low',
        }

    # --- Tier 3: name-based heuristics for edtech ---
    for cat_key, patterns in _EDTECH_NAME_PATTERNS.items():
        for pattern in patterns:
            if pattern in vendor_lower:
                return {
                    'ai_category': cat_key,
                    'ai_category_name': AI_REPLACEABILITY_CATEGORIES[cat_key]['name'],
                    'confidence': 'medium',
                }

    # Default for unmatched edtech
    return {
        'ai_category': 'supplemental_edtech',
        'ai_category_name': AI_REPLACEABILITY_CATEGORIES['supplemental_edtech']['name'],
        'confidence': 'low',
    }


def categorize_all_vendors_for_ai_analysis(
    categorized_df: pd.DataFrame,
    edtech_research_path: Optional[str] = None,
) -> pd.DataFrame:
    """
    Apply refined AI replaceability categories to all vendors.

    Args:
        categorized_df: DataFrame from pass1 with 'vendor' and 'category' columns.
        edtech_research_path: Path to edtech_research_v2.json.

    Returns:
        DataFrame with added ai_category, ai_category_name, ai_confidence columns.
    """
    # Load edtech research if provided
    research_lookup = {}
    if edtech_research_path and Path(edtech_research_path).exists():
        with open(edtech_research_path) as f:
            research_data = json.load(f)
        for entry in research_data:
            vendor_key = entry.get('vendor_name', '').upper().strip()
            research_lookup[vendor_key] = entry

    results = []
    for _, row in categorized_df.iterrows():
        vendor = row['vendor']
        pass1_cat = row['category']
        research = research_lookup.get(vendor.upper().strip())

        result = categorize_vendor_for_ai_analysis(vendor, pass1_cat, research)
        results.append(result)

    result_df = categorized_df.copy()
    result_df['ai_category'] = [r['ai_category'] for r in results]
    result_df['ai_category_name'] = [r['ai_category_name'] for r in results]
    result_df['ai_confidence'] = [r['confidence'] for r in results]

    return result_df


# ============================================================================
# Section D: Fund-Level Analysis
# ============================================================================

@dataclass
class FundProfile:
    """Profile of spending and activity for a single fund."""
    fund_code: str
    fund_name: str
    fund_category: str
    total_spending: float
    transaction_count: int
    vendor_count: int
    date_range: tuple  # (min_date, max_date)
    top_vendors: list  # list of (vendor, spending) tuples
    category_breakdown: dict  # ai_category -> spending
    ai_replaceable_spending: float  # spending in high/medium AI potential categories


def profile_all_funds(
    transactions_df: pd.DataFrame,
    vendor_categories_df: pd.DataFrame,
    top_n_vendors: int = 10,
) -> list[FundProfile]:
    """
    Build a FundProfile for every fund in the transactions.

    Args:
        transactions_df: Transactions with 'fund_code', 'vendor', 'amount', 'date'.
        vendor_categories_df: Vendors with 'vendor', 'ai_category' columns.
        top_n_vendors: How many top vendors to include per fund.

    Returns:
        List of FundProfile objects, sorted by total spending descending.
    """
    # Build vendor -> ai_category lookup
    vendor_cat = dict(zip(
        vendor_categories_df['vendor'].str.upper(),
        vendor_categories_df['ai_category'],
    ))

    # Categories where AI has high or medium replaceability potential
    ai_relevant_cats = {
        k for k, v in AI_REPLACEABILITY_CATEGORIES.items()
        if v['ai_potential'] in ('high', 'medium')
    }

    profiles = []
    valid = transactions_df.dropna(subset=['fund_code'])

    for fund_code, group in valid.groupby('fund_code'):
        info = get_fund_info(fund_code)

        # Top vendors
        vendor_spending = (
            group.groupby('vendor')['amount']
            .sum()
            .sort_values(ascending=False)
        )
        top_vendors = list(vendor_spending.head(top_n_vendors).items())

        # Category breakdown
        group_cats = group['vendor'].str.upper().map(vendor_cat).fillna('other')
        cat_breakdown = group.groupby(group_cats)['amount'].sum().to_dict()

        # AI-replaceable spending
        ai_spending = sum(
            v for k, v in cat_breakdown.items() if k in ai_relevant_cats
        )

        # Date range
        dates = pd.to_datetime(group['date'], errors='coerce').dropna()
        date_range = (
            (dates.min().strftime('%Y-%m-%d'), dates.max().strftime('%Y-%m-%d'))
            if len(dates) > 0
            else ('N/A', 'N/A')
        )

        profiles.append(FundProfile(
            fund_code=fund_code,
            fund_name=info['name'],
            fund_category=info.get('category', 'unknown'),
            total_spending=group['amount'].sum(),
            transaction_count=len(group),
            vendor_count=group['vendor'].nunique(),
            date_range=date_range,
            top_vendors=top_vendors,
            category_breakdown=cat_breakdown,
            ai_replaceable_spending=ai_spending,
        ))

    profiles.sort(key=lambda p: p.total_spending, reverse=True)
    return profiles


def build_fund_vendor_category_pivot(
    transactions_df: pd.DataFrame,
    vendor_categories_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Build a pivot table: (fund_code, ai_category, vendor) -> spending, count.

    Args:
        transactions_df: Transactions with 'fund_code', 'vendor', 'amount'.
        vendor_categories_df: Vendors with 'vendor', 'ai_category'.

    Returns:
        DataFrame with MultiIndex (fund_code, ai_category, vendor) and
        columns: total_spending, transaction_count.
    """
    vendor_cat = dict(zip(
        vendor_categories_df['vendor'].str.upper(),
        vendor_categories_df['ai_category'],
    ))

    df = transactions_df.dropna(subset=['fund_code']).copy()
    df['ai_category'] = df['vendor'].str.upper().map(vendor_cat).fillna('other')

    pivot = (
        df.groupby(['fund_code', 'ai_category', 'vendor'])
        .agg(total_spending=('amount', 'sum'), transaction_count=('amount', 'count'))
        .sort_values('total_spending', ascending=False)
    )

    return pivot


def build_fund_summary_table(fund_profiles: list[FundProfile]) -> pd.DataFrame:
    """
    Flatten FundProfile list into a summary DataFrame.

    Returns:
        DataFrame with one row per fund, columns: fund_code, fund_name,
        fund_category, total_spending, transaction_count, vendor_count,
        date_min, date_max, ai_replaceable_spending, ai_replaceable_pct.
    """
    rows = []
    for p in fund_profiles:
        rows.append({
            'fund_code': p.fund_code,
            'fund_name': p.fund_name,
            'fund_category': p.fund_category,
            'total_spending': p.total_spending,
            'transaction_count': p.transaction_count,
            'vendor_count': p.vendor_count,
            'date_min': p.date_range[0],
            'date_max': p.date_range[1],
            'ai_replaceable_spending': p.ai_replaceable_spending,
            'ai_replaceable_pct': (
                (p.ai_replaceable_spending / p.total_spending * 100)
                if p.total_spending > 0 else 0
            ),
        })
    return pd.DataFrame(rows)


# ============================================================================
# Section E: Cross-Reference & Export
# ============================================================================

def cross_reference_with_edtech_research(
    pivot: pd.DataFrame,
    edtech_research_path: str,
) -> pd.DataFrame:
    """
    Enrich the fund-vendor-category pivot with v2 research scores.

    Adds columns: classification, composite_score, replaceability_level,
    research_confidence from edtech_research_v2.json where available.
    """
    with open(edtech_research_path) as f:
        research_data = json.load(f)

    lookup = {}
    for entry in research_data:
        key = entry.get('vendor_name', '').upper().strip()
        lookup[key] = entry

    enriched = pivot.reset_index()

    def _lookup_field(vendor, field, default=''):
        entry = lookup.get(vendor.upper().strip())
        if entry:
            return entry.get(field, default)
        return default

    enriched['v2_classification'] = enriched['vendor'].apply(
        lambda v: _lookup_field(v, 'classification', '')
    )
    enriched['v2_composite_score'] = enriched['vendor'].apply(
        lambda v: _lookup_field(v, 'composite_score', None)
    )
    enriched['v2_replaceability_level'] = enriched['vendor'].apply(
        lambda v: _lookup_field(v, 'replaceability_level', '')
    )
    enriched['v2_research_confidence'] = enriched['vendor'].apply(
        lambda v: _lookup_field(v, 'research_confidence', '')
    )
    enriched['has_v2_research'] = enriched['v2_classification'] != ''

    return enriched


def identify_unresearched_vendors_by_fund(
    enriched_pivot: pd.DataFrame,
    spending_threshold: float = 50_000,
) -> pd.DataFrame:
    """
    Find vendors above spending_threshold that lack v2 research.

    Returns DataFrame sorted by total_spending descending.
    """
    unresearched = enriched_pivot[
        (~enriched_pivot['has_v2_research'])
        & (enriched_pivot['total_spending'] >= spending_threshold)
    ].copy()

    # Aggregate across funds for a vendor-level view
    vendor_totals = (
        unresearched.groupby('vendor')
        .agg(
            total_spending=('total_spending', 'sum'),
            fund_count=('fund_code', 'nunique'),
            ai_category=('ai_category', 'first'),
        )
        .sort_values('total_spending', ascending=False)
        .reset_index()
    )

    return vendor_totals


def export_fund_analysis(
    fund_profiles: list[FundProfile],
    pivot: pd.DataFrame,
    output_dir: str = 'data/fund_analysis',
) -> None:
    """
    Write fund_summary.csv and fund_vendor_category_pivot.csv.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    summary = build_fund_summary_table(fund_profiles)
    summary.to_csv(out / 'fund_summary.csv', index=False)

    pivot_flat = pivot.reset_index() if isinstance(pivot.index, pd.MultiIndex) else pivot
    pivot_flat.to_csv(out / 'fund_vendor_category_pivot.csv', index=False)

    print(f"Exported to {out}/:")
    print(f"  fund_summary.csv ({len(summary)} funds)")
    print(f"  fund_vendor_category_pivot.csv ({len(pivot_flat)} rows)")
