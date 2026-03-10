"""
AI-assisted vendor research and categorization for Dallas ISD spending analysis.

This module provides two-pass categorization:
1. Pass 1: Broad categorization of all vendors into major spending categories
2. Pass 2: Detailed research on EdTech/Instructional vendors for replaceability assessment

The replaceability framework uses a multi-dimensional scoring approach:
- Technical Buildability: Could a 4-person dev team build this?
- Content/IP Replaceability: How hard to replicate content?
- Switching Cost: Operational impact of replacement?
- Market Alternatives: Are there viable alternatives?
- Data Portability: Can you extract your data?
"""

import pandas as pd
import json
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
import anthropic
import os


# Vendor Classification Types
class VendorClassification(Enum):
    """Classification of vendor types for appropriate scoring."""
    PLATFORM = "platform"  # Software system (SIS, LMS, assessment)
    CURRICULUM_PLATFORM = "curriculum_platform"  # Content bundled with delivery platform
    CONTENT = "content"  # Licensed content without significant platform
    SERVICES = "services"  # Human-delivered (PD, consulting, tutoring)
    HYBRID = "hybrid"  # Mixed platform + services
    PHYSICAL = "physical"  # Hardware/materials (filter out)
    UNKNOWN = "unknown"  # Insufficient information (flag for research)


# Dimension weights for composite score calculation
DIMENSION_WEIGHTS = {
    'technical_buildability': 0.25,
    'content_ip': 0.25,
    'switching_cost': 0.20,
    'market_alternatives': 0.15,
    'data_portability': 0.15,
}


# Replaceability level thresholds
REPLACEABILITY_THRESHOLDS = {
    'high': (4.0, 5.0),      # Viable candidate for in-house development
    'medium': (3.0, 3.99),   # Possible with significant investment
    'low': (2.0, 2.99),      # Major barriers, not recommended
    'very_low': (1.0, 1.99), # Essentially irreplaceable
}


@dataclass
class DimensionScores:
    """Scores for each replaceability dimension (1-5 scale, 5 = most replaceable)."""
    technical_buildability: int = 0
    content_ip: int = 0
    switching_cost: int = 0
    market_alternatives: int = 0
    data_portability: int = 0


@dataclass
class DimensionRationales:
    """Rationales explaining each dimension score."""
    technical_buildability: str = ""
    content_ip: str = ""
    switching_cost: str = ""
    market_alternatives: str = ""
    data_portability: str = ""


@dataclass
class ServiceBreakdown:
    """Percentage breakdown of vendor service components."""
    software_licensing: int = 0
    professional_development: int = 0
    content_licensing: int = 0
    hardware_materials: int = 0
    ongoing_services: int = 0


@dataclass
class UserFootprint:
    """Estimated user counts for the vendor's products."""
    teachers: int = 0
    students: int = 0
    admin: int = 0


@dataclass
class VendorResearchResult:
    """Complete research result for a vendor with multi-dimensional scoring."""
    vendor_name: str
    classification: str  # VendorClassification value

    # Dimension scores (1-5)
    scores: DimensionScores = field(default_factory=DimensionScores)

    # Score rationales
    rationales: DimensionRationales = field(default_factory=DimensionRationales)

    # Composite score (calculated)
    composite_score: float = 0.0
    replaceability_level: str = "unknown"  # high|medium|low|very_low|none|unknown

    # Service breakdown (percentages)
    service_breakdown: ServiceBreakdown = field(default_factory=ServiceBreakdown)

    # Metadata
    criticality: str = "supplementary"  # core|important|supplementary
    user_footprint: UserFootprint = field(default_factory=UserFootprint)
    research_confidence: str = "unknown"  # high|medium|low|unknown

    # Existing fields retained
    primary_products: list = field(default_factory=list)
    product_descriptions: str = ""
    target_use_case: str = ""
    additional_notes: str = ""
    research_date: str = ""
    total_spending: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            'vendor_name': self.vendor_name,
            'classification': self.classification,
            'scores': asdict(self.scores),
            'rationales': asdict(self.rationales),
            'composite_score': self.composite_score,
            'replaceability_level': self.replaceability_level,
            'service_breakdown': asdict(self.service_breakdown),
            'criticality': self.criticality,
            'user_footprint': asdict(self.user_footprint),
            'research_confidence': self.research_confidence,
            'primary_products': self.primary_products,
            'product_descriptions': self.product_descriptions,
            'target_use_case': self.target_use_case,
            'additional_notes': self.additional_notes,
            'research_date': self.research_date,
            'total_spending': self.total_spending,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'VendorResearchResult':
        """Create from dictionary (e.g., from JSON)."""
        scores = DimensionScores(**data.get('scores', {}))
        rationales = DimensionRationales(**data.get('rationales', {}))
        service_breakdown = ServiceBreakdown(**data.get('service_breakdown', {}))
        user_footprint = UserFootprint(**data.get('user_footprint', {}))

        return cls(
            vendor_name=data.get('vendor_name', ''),
            classification=data.get('classification', 'unknown'),
            scores=scores,
            rationales=rationales,
            composite_score=data.get('composite_score', 0.0),
            replaceability_level=data.get('replaceability_level', 'unknown'),
            service_breakdown=service_breakdown,
            criticality=data.get('criticality', 'supplementary'),
            user_footprint=user_footprint,
            research_confidence=data.get('research_confidence', 'unknown'),
            primary_products=data.get('primary_products', []),
            product_descriptions=data.get('product_descriptions', ''),
            target_use_case=data.get('target_use_case', ''),
            additional_notes=data.get('additional_notes', ''),
            research_date=data.get('research_date', ''),
            total_spending=data.get('total_spending', 0.0),
        )


def calculate_composite_score(scores: DimensionScores) -> float:
    """
    Calculate weighted composite replaceability score.

    Args:
        scores: DimensionScores with values 1-5 for each dimension

    Returns:
        Weighted average score (1.0-5.0)
    """
    score_dict = asdict(scores)

    # Check if all scores are 0 (not scored)
    if all(v == 0 for v in score_dict.values()):
        return 0.0

    weighted_sum = sum(
        score_dict[dim] * weight
        for dim, weight in DIMENSION_WEIGHTS.items()
    )

    return round(weighted_sum, 2)


def determine_replaceability_level(
    composite_score: float,
    classification: str
) -> str:
    """
    Determine replaceability level from composite score and classification.

    Args:
        composite_score: Weighted average score (1.0-5.0)
        classification: Vendor classification type

    Returns:
        Replaceability level: high|medium|low|very_low|none|unknown
    """
    # Non-software vendors get 'none'
    if classification in ['services', 'physical']:
        return 'none'

    # Unknown classification gets 'unknown'
    if classification == 'unknown' or composite_score == 0:
        return 'unknown'

    # Map score to level
    for level, (min_score, max_score) in REPLACEABILITY_THRESHOLDS.items():
        if min_score <= composite_score <= max_score:
            return level

    return 'unknown'


def validate_scores(scores: DimensionScores) -> tuple[bool, list[str]]:
    """
    Validate that all dimension scores are in valid range (1-5).

    Args:
        scores: DimensionScores to validate

    Returns:
        Tuple of (is_valid, list of error messages)
    """
    errors = []
    score_dict = asdict(scores)

    for dim, value in score_dict.items():
        if not isinstance(value, int):
            errors.append(f"{dim}: must be an integer, got {type(value).__name__}")
        elif value < 0 or value > 5:
            errors.append(f"{dim}: must be 0-5, got {value}")

    return len(errors) == 0, errors


def migrate_legacy_research(legacy_data: dict) -> VendorResearchResult:
    """
    Migrate legacy research format to new multi-dimensional format.

    The legacy format has a single 'replaceability' field (high/medium/low/none).
    This function creates estimated dimension scores based on the legacy rating.

    Args:
        legacy_data: Dictionary in old format with single replaceability rating

    Returns:
        VendorResearchResult with estimated dimension scores
    """
    legacy_level = legacy_data.get('replaceability', 'unknown').lower()

    # Estimate dimension scores based on legacy level
    score_estimates = {
        'high': DimensionScores(
            technical_buildability=5,
            content_ip=4,
            switching_cost=4,
            market_alternatives=4,
            data_portability=4,
        ),
        'medium': DimensionScores(
            technical_buildability=3,
            content_ip=3,
            switching_cost=3,
            market_alternatives=3,
            data_portability=3,
        ),
        'low': DimensionScores(
            technical_buildability=2,
            content_ip=2,
            switching_cost=2,
            market_alternatives=2,
            data_portability=2,
        ),
        'none': DimensionScores(
            technical_buildability=0,
            content_ip=0,
            switching_cost=0,
            market_alternatives=0,
            data_portability=0,
        ),
    }

    # Determine classification from legacy data
    classification = 'unknown'
    rationale = legacy_data.get('replaceability_rationale', '').lower()
    products = ' '.join(legacy_data.get('primary_products', [])).lower()

    if legacy_level == 'none':
        if any(kw in rationale or kw in products for kw in ['physical', 'materials', 'furniture', 'supplies']):
            classification = 'physical'
        elif any(kw in rationale or kw in products for kw in ['professional development', 'consulting', 'training', 'tutoring']):
            classification = 'services'
    elif 'curriculum' in rationale or 'content' in rationale:
        classification = 'curriculum_platform'
    elif 'platform' in rationale or 'software' in rationale:
        classification = 'platform'

    scores = score_estimates.get(legacy_level, DimensionScores())
    composite = calculate_composite_score(scores)

    return VendorResearchResult(
        vendor_name=legacy_data.get('vendor_name', ''),
        classification=classification,
        scores=scores,
        rationales=DimensionRationales(
            technical_buildability=f"Migrated from legacy '{legacy_level}' rating",
            content_ip=f"Migrated from legacy '{legacy_level}' rating",
            switching_cost=f"Migrated from legacy '{legacy_level}' rating",
            market_alternatives=f"Migrated from legacy '{legacy_level}' rating",
            data_portability=f"Migrated from legacy '{legacy_level}' rating",
        ),
        composite_score=composite,
        replaceability_level=legacy_level if legacy_level != 'none' else 'none',
        research_confidence='low',  # Migrated data has lower confidence
        primary_products=legacy_data.get('primary_products', []),
        product_descriptions=legacy_data.get('product_descriptions', ''),
        target_use_case=legacy_data.get('target_use_case', ''),
        additional_notes=f"MIGRATED FROM LEGACY FORMAT. Original rationale: {legacy_data.get('replaceability_rationale', '')}",
        research_date=legacy_data.get('research_date', ''),
        total_spending=legacy_data.get('total_spending', 0.0),
    )


# Category definitions
MAJOR_CATEGORIES = {
    'payroll_benefits': 'Payroll, retirement, taxes, and employee benefits',
    'edtech_instructional': 'Educational technology, curriculum, instructional materials, assessment tools',
    'it_infrastructure': 'IT infrastructure, hardware, networking, security (non-instructional)',
    'facilities_construction': 'Facilities, construction, maintenance, utilities',
    'food_nutrition': 'Food services, cafeteria, nutrition programs',
    'transportation': 'Student transportation, buses, fleet services',
    'hr_professional_services': 'HR services, legal, consulting, professional development',
    'insurance_finance': 'Insurance, financial services, banking',
    'other': 'Other spending not fitting above categories'
}

# Legacy replaceability levels (kept for backward compatibility)
REPLACEABILITY_LEVELS = {
    'high': 'Software/platforms that could be built in-house (LMS, gradebooks, curriculum platforms, assessment tools)',
    'medium': 'Platforms with significant data integration requirements (SIS, analytics platforms)',
    'low': 'Specialized tools, content, or hardware with high barriers to replication',
    'very_low': 'Essentially irreplaceable - proprietary AI/ML, years of R&D',
    'none': 'Non-technical services, content licensing only, or hardware purchases'
}


def categorize_vendor_pass1(vendor_name, total_spending, transaction_count, use_api=False):
    """
    Pass 1: Quick categorization of a vendor into major spending category.

    Uses simple heuristics based on vendor name patterns. For ambiguous cases,
    can optionally use Claude API for better accuracy.

    Args:
        vendor_name: Name of the vendor
        total_spending: Total spending with this vendor
        transaction_count: Number of transactions
        use_api: Whether to use Claude API for categorization

    Returns:
        dict with category and confidence
    """
    vendor_lower = vendor_name.lower()

    # Heuristic-based categorization
    if any(x in vendor_lower for x in ['retirement', 'internal revenue', 'fica', 'social security']):
        return {'category': 'payroll_benefits', 'confidence': 'high', 'method': 'heuristic'}

    if any(x in vendor_lower for x in ['construction', 'contractor', 'builders', 'joint venture', 'beck', 'reeder']):
        return {'category': 'facilities_construction', 'confidence': 'high', 'method': 'heuristic'}

    if any(x in vendor_lower for x in ['reliant', 'energy', 'electricity', 'gas', 'water', 'utility']):
        return {'category': 'facilities_construction', 'confidence': 'medium', 'method': 'heuristic'}

    if any(x in vendor_lower for x in ['insurance', 'healthcare', 'health special risk', 'dearborn']):
        return {'category': 'insurance_finance', 'confidence': 'high', 'method': 'heuristic'}

    if any(x in vendor_lower for x in ['food', 'dairy', 'cafeteria', 'nutrition', 'meal', 'lunch']):
        return {'category': 'food_nutrition', 'confidence': 'high', 'method': 'heuristic'}

    if any(x in vendor_lower for x in ['bus', 'transportation', 'fleet', 'longhorn bus']):
        return {'category': 'transportation', 'confidence': 'high', 'method': 'heuristic'}

    # EdTech/Instructional indicators
    if any(x in vendor_lower for x in [
        'amplify', 'curriculum', 'learning', 'education', 'scholastic', 'textbook',
        'instructional', 'assessment', 'great minds', 'eureka', 'zearn', 'imagine learning',
        'renaissance', 'lexia', 'istation', 'dreambox', 'classwork'
    ]):
        return {'category': 'edtech_instructional', 'confidence': 'high', 'method': 'heuristic'}

    # IT infrastructure (but not instructional)
    if any(x in vendor_lower for x in [
        'lenovo', 'dell', 'apple', 'cdw', 'microsoft', 'oracle', 'network', 'security',
        'convergint', 'digi security', 'cisco', 'hardware'
    ]):
        # Could be either IT infrastructure or instructional tech - need more context
        if any(x in vendor_lower for x in ['chromebook', 'ipad', 'student device']):
            return {'category': 'edtech_instructional', 'confidence': 'medium', 'method': 'heuristic'}
        else:
            return {'category': 'it_infrastructure', 'confidence': 'medium', 'method': 'heuristic'}

    # HR/Professional services
    if any(x in vendor_lower for x in ['consulting', 'legal', 'audit', 'professional development', 'training']):
        return {'category': 'hr_professional_services', 'confidence': 'medium', 'method': 'heuristic'}

    # Default to uncertain
    return {'category': 'other', 'confidence': 'low', 'method': 'heuristic'}


def categorize_vendors_pass1_batch(vendor_df, output_file='data/vendors/vendor_categorization_pass1.csv'):
    """
    Perform Pass 1 categorization on all vendors using heuristics.

    Args:
        vendor_df: DataFrame with vendor data (must have 'vendor', 'total_spending', 'transaction_count')
        output_file: Where to save results

    Returns:
        DataFrame with categorization results
    """
    print("=" * 80)
    print("PASS 1: BROAD VENDOR CATEGORIZATION")
    print("=" * 80)
    print(f"Categorizing {len(vendor_df):,} vendors...")
    print()

    results = []
    for idx, row in vendor_df.iterrows():
        result = categorize_vendor_pass1(
            row['vendor'],
            row['total_spending'],
            row['transaction_count']
        )

        results.append({
            'vendor': row['vendor'],
            'total_spending': row['total_spending'],
            'transaction_count': row['transaction_count'],
            'category': result['category'],
            'confidence': result['confidence'],
            'categorization_method': result['method']
        })

        if (idx + 1) % 1000 == 0:
            print(f"  Processed {idx + 1:,} vendors...")

    result_df = pd.DataFrame(results)

    # Save results
    result_df.to_csv(output_file, index=False)
    print(f"\n✓ Saved Pass 1 categorization to {output_file}")

    # Print summary
    print("\nCategorization Summary:")
    print("-" * 80)

    category_summary = result_df.groupby('category').agg({
        'vendor': 'count',
        'total_spending': 'sum'
    }).sort_values('total_spending', ascending=False)

    total_spending = result_df['total_spending'].sum()

    for category, row in category_summary.iterrows():
        pct = (row['total_spending'] / total_spending) * 100
        print(f"{category:30s}: {int(row['vendor']):5d} vendors, ${row['total_spending']:>15,.2f} ({pct:5.1f}%)")

    print()
    print(f"Confidence levels:")
    confidence_counts = result_df['confidence'].value_counts()
    for conf, count in confidence_counts.items():
        print(f"  {conf}: {count:,} vendors")

    return result_df


def identify_edtech_vendors_for_pass2(categorized_df, spending_threshold=0.80):
    """
    Identify EdTech/Instructional vendors for detailed Pass 2 research.

    Focus on vendors that represent top X% of edtech/instructional spending.

    Args:
        categorized_df: DataFrame from Pass 1 categorization
        spending_threshold: Cumulative spending threshold (e.g., 0.80 for 80%)

    Returns:
        DataFrame with prioritized EdTech vendors for detailed research
    """
    # Filter to EdTech/Instructional category
    edtech_vendors = categorized_df[
        categorized_df['category'] == 'edtech_instructional'
    ].copy()

    # Sort by spending
    edtech_vendors = edtech_vendors.sort_values('total_spending', ascending=False)

    # Calculate cumulative percentage
    total_edtech_spending = edtech_vendors['total_spending'].sum()
    edtech_vendors['cumulative_spending'] = edtech_vendors['total_spending'].cumsum()
    edtech_vendors['cumulative_pct'] = edtech_vendors['cumulative_spending'] / total_edtech_spending

    # Identify vendors to research in detail
    priority_vendors = edtech_vendors[
        edtech_vendors['cumulative_pct'] <= spending_threshold
    ].copy()

    priority_vendors['research_priority'] = 'high'

    # Mark remaining edtech vendors as low priority
    remaining_vendors = edtech_vendors[
        edtech_vendors['cumulative_pct'] > spending_threshold
    ].copy()
    remaining_vendors['research_priority'] = 'low'

    print("=" * 80)
    print("EDTECH VENDORS IDENTIFIED FOR PASS 2 RESEARCH")
    print("=" * 80)
    print(f"Total EdTech/Instructional vendors: {len(edtech_vendors):,}")
    print(f"Total EdTech spending: ${total_edtech_spending:,.2f}")
    print()
    print(f"High priority (top {spending_threshold*100:.0f}% of spending): {len(priority_vendors)} vendors")
    print(f"  Spending: ${priority_vendors['total_spending'].sum():,.2f}")
    print(f"Low priority: {len(remaining_vendors)} vendors")
    print()

    print("Top 30 EdTech vendors for detailed research:")
    print("-" * 80)
    for idx, row in priority_vendors.head(30).iterrows():
        print(f"{row.name+1:3d}. {row['vendor'][:55]:55s} ${row['total_spending']:>12,.2f}")

    return pd.concat([priority_vendors, remaining_vendors])


def get_v2_research_prompt(vendor_name: str, total_spending: float) -> str:
    """
    Generate the v2 multi-dimensional research prompt.

    Args:
        vendor_name: Name of the vendor
        total_spending: Total spending with vendor

    Returns:
        Formatted prompt string for Claude API
    """
    return f'''Research the educational technology vendor "{vendor_name}" for Dallas ISD.
Total spending (Sept 2021 - Aug 2025): ${total_spending:,.2f}

CLASSIFICATION: First, classify this vendor:
- platform: Software system (SIS, LMS, assessment platform)
- curriculum_platform: Content bundled with delivery platform
- content: Licensed content without significant platform
- services: Human-delivered (PD, consulting, tutoring)
- hybrid: Mixed platform + services
- physical: Hardware/materials (not software)
- unknown: Insufficient information available

DIMENSION SCORES (1-5 scale, where 5 = most replaceable):

1. TECHNICAL BUILDABILITY - Could a 4-person dev team build this?
   5: Standard CRUD, common patterns (basic LMS, gradebook)
   4: Moderate complexity, some integrations
   3: Significant integrations, 12-18 month build
   2: Complex algorithms, extensive compliance needs
   1: Proprietary AI/ML, years of R&D required
   Assess: database complexity, real-time needs, integrations, compliance, algorithms

2. CONTENT/IP REPLACEABILITY - How hard to replicate content?
   5: No proprietary content, platform-only
   4: Generic content, OER alternatives exist
   3: Curated content requiring SME expertise
   2: Extensive standards-aligned curriculum
   1: Research-backed methodology, irreplaceable IP
   Assess: content volume, standards work, multimedia, localization, pedagogy research

3. SWITCHING COST - Operational impact of replacement?
   5: Minimal, few users, supplementary tool
   4: Some retraining, limited data migration
   3: Moderate disruption, significant retraining
   2: Major disruption, multi-year transition
   1: Mission-critical, catastrophic to switch
   Assess: user count, training hours, data migration, dependencies, timing constraints

4. MARKET ALTERNATIVES - Are there viable alternatives?
   5: Multiple competitors, open-source options
   4: Several alternatives, competitive market
   3: Limited alternatives, 2-3 major players
   2: Near-monopoly, few substitutes
   1: Sole provider, patent-protected, legally mandated
   Assess: competitor count, open-source, patents, regulatory requirements

5. DATA PORTABILITY - Can you extract your data?
   5: Open standards, full export, documented APIs
   4: Good export, standard formats
   3: Partial export, some proprietary formats
   2: Limited export, significant data locked
   1: Proprietary formats, no export, data hostage
   Assess: export formats, API docs, historical data access, portfolio portability

SERVICE BREAKDOWN: Estimate percentages (must sum to 100):
- software_licensing: % for platform/software access
- professional_development: % for training/PD services
- content_licensing: % for curriculum/content
- hardware_materials: % for physical goods
- ongoing_services: % for support/consulting

CRITICALITY: How critical is this to daily operations?
- core: Daily operations depend on it
- important: Significant but not critical
- supplementary: Nice to have

For services/physical vendors: Set all dimension scores to 0.

Respond in JSON format:
{{
  "vendor_name": "{vendor_name}",
  "classification": "platform|curriculum_platform|content|services|hybrid|physical|unknown",
  "scores": {{
    "technical_buildability": 1-5,
    "content_ip": 1-5,
    "switching_cost": 1-5,
    "market_alternatives": 1-5,
    "data_portability": 1-5
  }},
  "rationales": {{
    "technical_buildability": "...",
    "content_ip": "...",
    "switching_cost": "...",
    "market_alternatives": "...",
    "data_portability": "..."
  }},
  "service_breakdown": {{
    "software_licensing": 0-100,
    "professional_development": 0-100,
    "content_licensing": 0-100,
    "hardware_materials": 0-100,
    "ongoing_services": 0-100
  }},
  "criticality": "core|important|supplementary",
  "research_confidence": "high|medium|low|unknown",
  "primary_products": ["..."],
  "product_descriptions": "...",
  "target_use_case": "...",
  "additional_notes": "..."
}}'''


def research_vendor_with_ai_v2(vendor_name: str, total_spending: float, api_key: Optional[str] = None) -> VendorResearchResult:
    """
    Use Claude API to research a vendor with multi-dimensional scoring (v2 format).

    Args:
        vendor_name: Name of the vendor
        total_spending: Total spending with vendor
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)

    Returns:
        VendorResearchResult with full multi-dimensional assessment
    """
    if api_key is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set and no api_key provided")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = get_v2_research_prompt(vendor_name, total_spending)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Return error result
            return VendorResearchResult(
                vendor_name=vendor_name,
                classification='unknown',
                research_confidence='unknown',
                additional_notes=f"Error: Could not parse JSON response. Raw: {response_text[:500]}",
                research_date=datetime.now().isoformat(),
                total_spending=total_spending,
            )

        # Parse scores
        scores_data = result.get('scores', {})
        scores = DimensionScores(
            technical_buildability=int(scores_data.get('technical_buildability', 0)),
            content_ip=int(scores_data.get('content_ip', 0)),
            switching_cost=int(scores_data.get('switching_cost', 0)),
            market_alternatives=int(scores_data.get('market_alternatives', 0)),
            data_portability=int(scores_data.get('data_portability', 0)),
        )

        # Parse rationales
        rationales_data = result.get('rationales', {})
        rationales = DimensionRationales(
            technical_buildability=rationales_data.get('technical_buildability', ''),
            content_ip=rationales_data.get('content_ip', ''),
            switching_cost=rationales_data.get('switching_cost', ''),
            market_alternatives=rationales_data.get('market_alternatives', ''),
            data_portability=rationales_data.get('data_portability', ''),
        )

        # Parse service breakdown
        breakdown_data = result.get('service_breakdown', {})
        service_breakdown = ServiceBreakdown(
            software_licensing=int(breakdown_data.get('software_licensing', 0)),
            professional_development=int(breakdown_data.get('professional_development', 0)),
            content_licensing=int(breakdown_data.get('content_licensing', 0)),
            hardware_materials=int(breakdown_data.get('hardware_materials', 0)),
            ongoing_services=int(breakdown_data.get('ongoing_services', 0)),
        )

        # Calculate composite score
        classification = result.get('classification', 'unknown')
        composite = calculate_composite_score(scores)
        level = determine_replaceability_level(composite, classification)

        return VendorResearchResult(
            vendor_name=result.get('vendor_name', vendor_name),
            classification=classification,
            scores=scores,
            rationales=rationales,
            composite_score=composite,
            replaceability_level=level,
            service_breakdown=service_breakdown,
            criticality=result.get('criticality', 'supplementary'),
            research_confidence=result.get('research_confidence', 'medium'),
            primary_products=result.get('primary_products', []),
            product_descriptions=result.get('product_descriptions', ''),
            target_use_case=result.get('target_use_case', ''),
            additional_notes=result.get('additional_notes', ''),
            research_date=datetime.now().isoformat(),
            total_spending=total_spending,
        )

    except Exception as e:
        return VendorResearchResult(
            vendor_name=vendor_name,
            classification='unknown',
            research_confidence='unknown',
            additional_notes=f"Error: {str(e)}",
            research_date=datetime.now().isoformat(),
            total_spending=total_spending,
        )


def research_vendor_with_ai(vendor_name, total_spending, api_key=None):
    """
    Use Claude API to research a vendor and assess replaceability.
    LEGACY FUNCTION - kept for backward compatibility.
    Use research_vendor_with_ai_v2() for new multi-dimensional scoring.

    Args:
        vendor_name: Name of the vendor
        total_spending: Total spending with vendor
        api_key: Anthropic API key (or set ANTHROPIC_API_KEY env var)

    Returns:
        dict with research results (legacy format)
    """
    if api_key is None:
        api_key = os.environ.get('ANTHROPIC_API_KEY')

    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set and no api_key provided")

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Research the educational technology vendor "{vendor_name}" and provide a detailed assessment.

Total spending by Dallas ISD (Sept 2021 - Aug 2025): ${total_spending:,.2f}

Please provide:

1. **Primary Products/Services**: What specific educational technology products or services does this vendor provide? List the main platforms, software, curriculum materials, or tools.

2. **Target Use Case**: How are these products typically used in K-12 schools? (e.g., learning management, assessment, curriculum delivery, student information system, professional development, etc.)

3. **Replaceability Assessment**: Assess how feasible it would be for a school district to build an in-house alternative with a small dev team (2-4 developers) using modern tools and AI-assisted coding. Use these criteria:

   - **HIGH**: Software platforms that could be built in-house within 1-2 years
     * Examples: Learning management systems, gradebooks, basic assessment tools, curriculum delivery platforms
     * Characteristics: Standard CRUD operations, common educational workflows, well-defined requirements

   - **MEDIUM**: Platforms requiring significant integration or specialized features
     * Examples: Student information systems, analytics platforms, tools requiring extensive third-party integrations
     * Characteristics: Complex data integrations, specialized algorithms, significant compliance requirements

   - **LOW**: Highly specialized tools or content-dependent products
     * Examples: Adaptive learning engines with proprietary algorithms, specialized assessment tools, curriculum content
     * Characteristics: Requires specialized expertise, proprietary content/algorithms, significant R&D investment

   - **NONE**: Non-technical services, pure content, or hardware
     * Examples: Professional development services, textbook content licensing, physical materials
     * Characteristics: Not software-based, primarily human services or physical goods

4. **Replaceability Rationale**: Explain your assessment in 2-3 sentences, considering:
   - Technical complexity
   - Required domain expertise
   - Content vs. platform distinction
   - Integration requirements
   - Time to build vs. maintain

Please format your response as JSON:
{{
  "vendor_name": "{vendor_name}",
  "primary_products": ["product 1", "product 2"],
  "product_descriptions": "Brief description of main products",
  "target_use_case": "How it's used in schools",
  "replaceability": "high|medium|low|none",
  "replaceability_rationale": "Explanation here",
  "additional_notes": "Any other relevant information"
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}]
        )

        response_text = message.content[0].text

        # Try to extract JSON from response
        import re
        json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Fallback if JSON parsing fails
            result = {
                'vendor_name': vendor_name,
                'raw_response': response_text,
                'error': 'Could not parse JSON response'
            }

        result['research_date'] = datetime.now().isoformat()
        result['total_spending'] = total_spending

        return result

    except Exception as e:
        return {
            'vendor_name': vendor_name,
            'error': str(e),
            'research_date': datetime.now().isoformat(),
            'total_spending': total_spending
        }


def research_edtech_vendors_pass2(edtech_df, priority='high', batch_size=5, api_key=None):
    """
    Perform Pass 2 detailed research on EdTech vendors using Claude API.

    Args:
        edtech_df: DataFrame from identify_edtech_vendors_for_pass2
        priority: 'high' or 'low' or 'all'
        batch_size: Number of vendors to research in one run (for checkpointing)
        api_key: Anthropic API key

    Returns:
        DataFrame with research results
    """
    # Filter by priority
    if priority == 'all':
        vendors_to_research = edtech_df
    else:
        vendors_to_research = edtech_df[edtech_df['research_priority'] == priority]

    print("=" * 80)
    print(f"PASS 2: DETAILED EDTECH VENDOR RESEARCH")
    print("=" * 80)
    print(f"Researching {len(vendors_to_research)} {priority}-priority EdTech vendors...")
    print(f"Total spending: ${vendors_to_research['total_spending'].sum():,.2f}")
    print()

    results = []
    output_file = f'data/vendors/edtech_research_pass2_{priority}.json'

    # Load existing results if file exists
    if Path(output_file).exists():
        with open(output_file, 'r') as f:
            existing_results = json.load(f)
        print(f"Found {len(existing_results)} existing research results")
        results = existing_results
        researched_vendors = {r['vendor_name'] for r in results}
    else:
        researched_vendors = set()

    for idx, row in vendors_to_research.iterrows():
        vendor = row['vendor']

        # Skip if already researched
        if vendor in researched_vendors:
            print(f"[{idx+1}/{len(vendors_to_research)}] {vendor} - Already researched, skipping")
            continue

        print(f"[{idx+1}/{len(vendors_to_research)}] Researching {vendor}...", end=' ')

        try:
            result = research_vendor_with_ai(vendor, row['total_spending'], api_key=api_key)
            results.append(result)
            researched_vendors.add(vendor)

            # Display result
            if 'replaceability' in result:
                print(f"✓ {result['replaceability'].upper()}")
                print(f"    Products: {result.get('product_descriptions', 'N/A')[:80]}")
            else:
                print(f"✗ Error: {result.get('error', 'Unknown error')}")

            # Save progress after each vendor
            with open(output_file, 'w') as f:
                json.dump(results, f, indent=2)

        except Exception as e:
            print(f"✗ Error: {e}")
            continue

        # Small delay to avoid rate limits
        import time
        time.sleep(1)

    print()
    print("=" * 80)
    print(f"Research complete: {len(results)} vendors researched")
    print(f"✓ Results saved to {output_file}")

    # Create summary DataFrame
    summary_df = pd.DataFrame(results)
    return summary_df


def research_edtech_vendors_pass2_v2(edtech_df, priority='high', api_key=None):
    """
    Perform Pass 2 detailed research on EdTech vendors using the v2 multi-dimensional framework.

    Args:
        edtech_df: DataFrame from identify_edtech_vendors_for_pass2
        priority: 'high' or 'low' or 'all'
        api_key: Anthropic API key

    Returns:
        List of VendorResearchResult objects
    """
    # Filter by priority
    if priority == 'all':
        vendors_to_research = edtech_df
    else:
        vendors_to_research = edtech_df[edtech_df['research_priority'] == priority]

    print("=" * 80)
    print(f"PASS 2 v2: MULTI-DIMENSIONAL EDTECH VENDOR RESEARCH")
    print("=" * 80)
    print(f"Researching {len(vendors_to_research)} {priority}-priority EdTech vendors...")
    print(f"Total spending: ${vendors_to_research['total_spending'].sum():,.2f}")
    print()

    results = []
    output_file = f'data/vendors/edtech_research_v2.json'

    # Load existing results if file exists
    if Path(output_file).exists():
        with open(output_file, 'r') as f:
            existing_data = json.load(f)
        print(f"Found {len(existing_data)} existing research results")
        results = [VendorResearchResult.from_dict(d) for d in existing_data]
        researched_vendors = {r.vendor_name for r in results}
    else:
        researched_vendors = set()

    for idx, row in vendors_to_research.iterrows():
        vendor = row['vendor']

        # Skip if already researched
        if vendor in researched_vendors:
            print(f"[{idx+1}/{len(vendors_to_research)}] {vendor} - Already researched, skipping")
            continue

        print(f"[{idx+1}/{len(vendors_to_research)}] Researching {vendor}...", end=' ')

        try:
            result = research_vendor_with_ai_v2(vendor, row['total_spending'], api_key=api_key)
            results.append(result)
            researched_vendors.add(vendor)

            # Display result
            print(f"✓ {result.replaceability_level.upper()} (score: {result.composite_score:.2f})")
            print(f"    Classification: {result.classification}")
            print(f"    Products: {result.product_descriptions[:60]}...")

            # Save progress after each vendor
            with open(output_file, 'w') as f:
                json.dump([r.to_dict() for r in results], f, indent=2)

        except Exception as e:
            print(f"✗ Error: {e}")
            continue

        # Small delay to avoid rate limits
        import time
        time.sleep(1)

    print()
    print("=" * 80)
    print(f"Research complete: {len(results)} vendors researched")
    print(f"✓ Results saved to {output_file}")

    # Print summary statistics
    print()
    print("Summary by Replaceability Level:")
    level_counts = {}
    level_spending = {}
    for r in results:
        level = r.replaceability_level
        level_counts[level] = level_counts.get(level, 0) + 1
        level_spending[level] = level_spending.get(level, 0) + r.total_spending

    for level in ['high', 'medium', 'low', 'very_low', 'none', 'unknown']:
        if level in level_counts:
            print(f"  {level.upper():10s}: {level_counts[level]:2d} vendors, ${level_spending[level]:>12,.2f}")

    return results


def migrate_legacy_research_file(legacy_path: str, output_path: str):
    """
    Migrate a legacy research JSON file to v2 format.

    Args:
        legacy_path: Path to legacy JSON file
        output_path: Path for output v2 JSON file
    """
    print(f"Migrating {legacy_path} to v2 format...")

    with open(legacy_path, 'r') as f:
        legacy_data = json.load(f)

    migrated = []
    for item in legacy_data:
        result = migrate_legacy_research(item)
        migrated.append(result)
        print(f"  ✓ {result.vendor_name}: {result.replaceability_level} (legacy)")

    with open(output_path, 'w') as f:
        json.dump([r.to_dict() for r in migrated], f, indent=2)

    print(f"\n✓ Migrated {len(migrated)} vendors to {output_path}")
    return migrated


if __name__ == "__main__":
    # Load vendor list
    vendor_df = pd.read_csv('data/vendors/vendor_list.csv')

    # Run Pass 1 categorization
    categorized_df = categorize_vendors_pass1_batch(vendor_df)

    # Identify EdTech vendors for Pass 2
    edtech_priority = identify_edtech_vendors_for_pass2(categorized_df, spending_threshold=0.85)

    # Save EdTech priority list
    edtech_priority.to_csv('data/vendors/edtech_vendors_for_research.csv', index=False)
    print(f"\n✓ Saved EdTech priority list to data/vendors/edtech_vendors_for_research.csv")
