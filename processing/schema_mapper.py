# ==================================================
# PROJECT OCTOPUS — ADAPTIVE SCHEMA MAPPER V2
# ==================================================

import re
from difflib import SequenceMatcher

import pandas as pd


# ==================================================
# CANONICAL SCHEMA
# ==================================================

CANONICAL_FIELDS = {
    "asset_id": {
        "terms": [
            "asset id",
            "asset no",
            "asset number",
            "asset code",
            "asset identifier",
            "equipment id",
            "equipment no",
            "equipment number",
            "device id",
            "device no",
            "device number",
            "machine id",
            "machine no",
            "machine number",
            "item id",
            "item no",
            "item number",
            "identifier",
            "id"
        ],
        "patterns": ["id_like"]
    },

    "asset_name": {
        "terms": [
            "asset name",
            "asset description",
            "equipment name",
            "equipment description",
            "device name",
            "device description",
            "machine name",
            "machine description",
            "item name",
            "item description",
            "product name",
            "description",
            "name",
            "title"
        ],
        "patterns": ["text_description"]
    },

    "location": {
        "terms": [
            "location",
            "location name",
            "location code",
            "current location",
            "loc",
            "place",
            "site",
            "site location",
            "room",
            "area",
            "zone",
            "gallery",
            "building",
            "facility",
            "floor",
            "lab"
        ],
        "patterns": ["location_like"]
    },

    "status": {
        "terms": [
            "status",
            "current status",
            "state",
            "current state",
            "condition",
            "current condition",
            "health",
            "availability",
            "operational status",
            "operating status",
            "mode"
        ],
        "patterns": ["status_like"]
    },

    "last_updated": {
        "terms": [
            "last updated",
            "last update",
            "updated",
            "update time",
            "updated time",
            "updated date",
            "modified",
            "modified time",
            "modified date",
            "modification time",
            "changed",
            "change time",
            "timestamp",
            "time stamp",
            "last modified",
            "last changed",
            "sync time",
            "refresh time"
        ],
        "patterns": ["datetime_like"]
    }
}


# ==================================================
# TEXT NORMALIZATION
# ==================================================

def normalize_text(value: str) -> str:

    value = str(value).strip().lower()

    value = re.sub(
        r"([a-z])([A-Z])",
        r"\1 \2",
        value
    )

    value = value.replace("_", " ")
    value = value.replace("-", " ")

    value = re.sub(
        r"[^a-z0-9 ]",
        " ",
        value
    )

    value = re.sub(
        r"\s+",
        " ",
        value
    )

    return value.strip()


def tokenize(value: str) -> list[str]:

    normalized = normalize_text(value)

    if not normalized:
        return []

    return normalized.split()


# ==================================================
# COLUMN NAME SIMILARITY
# ==================================================

def column_name_score(
    column_name: str,
    canonical_field: str
) -> float:

    source = normalize_text(
        column_name
    )

    if not source:
        return 0.0

    terms = CANONICAL_FIELDS[
        canonical_field
    ]["terms"]

    source_tokens = set(
        tokenize(source)
    )

    best_score = 0.0

    for term in terms:

        target = normalize_text(
            term
        )

        target_tokens = set(
            tokenize(target)
        )

        intersection = (
            source_tokens &
            target_tokens
        )

        union = (
            source_tokens |
            target_tokens
        )

        token_score = 0.0

        if union:
            token_score = (
                len(intersection) /
                len(union)
            )

        sequence_score = SequenceMatcher(
            None,
            source,
            target
        ).ratio()

        score = (
            0.65 * token_score
            +
            0.35 * sequence_score
        )

        best_score = max(
            best_score,
            score
        )

    return round(
        best_score,
        2
    )


# ==================================================
# VALUE PATTERN DETECTION
# ==================================================

def detect_value_patterns(
    dataframe: pd.DataFrame,
    column_name: str
) -> dict:

    series = dataframe[
        column_name
    ].dropna()

    if series.empty:

        return {
            "id_like": 0.0,
            "text_description": 0.0,
            "location_like": 0.0,
            "status_like": 0.0,
            "datetime_like": 0.0
        }

    values = (
        series
        .astype(str)
        .str.strip()
        .head(50)
    )

    total = len(values)


    # --------------------------------------------------
    # ID PATTERN
    # --------------------------------------------------

    id_matches = 0

    for value in values:

        if re.fullmatch(
            r"[A-Za-z]{0,6}[-_]?\d{1,12}",
            value
        ):
            id_matches += 1

    id_score = (
        id_matches / total
    )


    # --------------------------------------------------
    # DATETIME PATTERN
    # --------------------------------------------------

    converted = pd.to_datetime(
        values,
        errors="coerce",
        format="mixed"
    )

    datetime_score = (
        converted.notna().mean()
    )


    # --------------------------------------------------
    # LOCATION PATTERN
    # --------------------------------------------------

    location_words = [
        "gallery",
        "room",
        "site",
        "zone",
        "area",
        "floor",
        "building",
        "facility",
        "lab",
        "block",
        "office"
    ]

    location_matches = sum(
        any(
            word in value.lower()
            for word in location_words
        )
        for value in values
    )

    location_score = (
        location_matches / total
    )


    # --------------------------------------------------
    # STATUS PATTERN
    # --------------------------------------------------

    status_words = [
        "active",
        "inactive",
        "maintenance",
        "offline",
        "online",
        "available",
        "unavailable",
        "working",
        "fault",
        "error",
        "failed",
        "running",
        "stopped",
        "operational"
    ]

    status_matches = sum(
        any(
            word in value.lower()
            for word in status_words
        )
        for value in values
    )

    status_score = (
        status_matches / total
    )


    # --------------------------------------------------
    # DESCRIPTION PATTERN
    # --------------------------------------------------

    average_length = (
        values.str.len().mean()
    )

    unique_ratio = (
        values.nunique() / total
    )

    if average_length >= 5:

        description_score = min(
            1.0,
            0.55 +
            (unique_ratio * 0.45)
        )

    else:

        description_score = 0.15


    return {
        "id_like": round(
            id_score,
            2
        ),

        "text_description": round(
            description_score,
            2
        ),

        "location_like": round(
            location_score,
            2
        ),

        "status_like": round(
            status_score,
            2
        ),

        "datetime_like": round(
            datetime_score,
            2
        )
    }


# ==================================================
# VALUE SCORE
# ==================================================

def value_pattern_score(
    dataframe: pd.DataFrame,
    column_name: str,
    canonical_field: str
) -> float:

    patterns = detect_value_patterns(
        dataframe,
        column_name
    )

    expected_patterns = (
        CANONICAL_FIELDS[
            canonical_field
        ]["patterns"]
    )

    if not expected_patterns:
        return 0.0

    return max(
        patterns.get(
            pattern,
            0.0
        )
        for pattern in expected_patterns
    )


# ==================================================
# DIRECT SEMANTIC BOOST
# ==================================================

def semantic_boost(
    column_name: str,
    canonical_field: str
) -> float:

    tokens = set(
        tokenize(column_name)
    )

    boost = 0.0


    # ID
    if canonical_field == "asset_id":

        if tokens & {
            "id",
            "no",
            "number",
            "num",
            "code",
            "identifier"
        }:
            boost += 0.30

        if tokens & {
            "asset",
            "equipment",
            "device",
            "machine",
            "item"
        }:
            boost += 0.20


    # NAME
    elif canonical_field == "asset_name":

        if tokens & {
            "name",
            "description",
            "desc",
            "title"
        }:
            boost += 0.40

        if tokens & {
            "asset",
            "equipment",
            "device",
            "machine",
            "item",
            "product"
        }:
            boost += 0.20


    # LOCATION
    elif canonical_field == "location":

        if tokens & {
            "location",
            "loc",
            "place",
            "site",
            "room",
            "area",
            "zone",
            "gallery",
            "building",
            "facility",
            "floor",
            "lab"
        }:
            boost += 0.50


    # STATUS
    elif canonical_field == "status":

        if tokens & {
            "status",
            "state",
            "condition",
            "health",
            "availability",
            "operational",
            "mode"
        }:
            boost += 0.50


    # LAST UPDATED
    elif canonical_field == "last_updated":

        if tokens & {
            "updated",
            "update",
            "modified",
            "modification",
            "changed",
            "change",
            "timestamp",
            "time",
            "date",
            "sync",
            "refresh"
        }:
            boost += 0.50


    return min(
        boost,
        0.60
    )


# ==================================================
# FINAL CONFIDENCE
# ==================================================

def calculate_confidence(
    dataframe: pd.DataFrame,
    column_name: str,
    canonical_field: str
) -> float:

    name_score = column_name_score(
        column_name,
        canonical_field
    )

    value_score = value_pattern_score(
        dataframe,
        column_name,
        canonical_field
    )

    boost = semantic_boost(
        column_name,
        canonical_field
    )

    confidence = (
        (name_score * 0.40)
        +
        (value_score * 0.40)
        +
        (boost * 0.20)
    )

    return round(
        min(
            confidence,
            1.0
        ),
        2
    )


# ==================================================
# BEST MATCH
# ==================================================

def find_best_match(
    dataframe: pd.DataFrame,
    column_name: str
) -> dict:

    candidates = []

    for canonical_field in CANONICAL_FIELDS:

        confidence = calculate_confidence(
            dataframe,
            column_name,
            canonical_field
        )

        candidates.append({
            "canonical_field":
                canonical_field,

            "confidence":
                confidence
        })


    candidates.sort(
        key=lambda item:
        item["confidence"],
        reverse=True
    )


    best = candidates[0]


    if best["confidence"] >= 0.80:

        decision = "AUTO_MAP"

    elif best["confidence"] >= 0.60:

        decision = "REVIEW"

    else:

        decision = "UNMAPPED"


    return {
        "source_column":
            column_name,

        "canonical_field":
            best["canonical_field"],

        "confidence":
            best["confidence"],

        "decision":
            decision,

        "candidates":
            candidates
    }


# ==================================================
# MAP COMPLETE DATAFRAME
# ==================================================

def map_dataframe(
    dataframe: pd.DataFrame
) -> list[dict]:

    results = []

    for column in dataframe.columns:

        results.append(
            find_best_match(
                dataframe,
                column
            )
        )

    return results