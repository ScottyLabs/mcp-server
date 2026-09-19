"""Configuration and curated metadata for the bus MCP service."""

import os

from mcp_server.services.bus.models import KnownStop, NeighborhoodDestinationRule


API_BASE_URL = os.environ.get(
    "BUS_SIGN_API_URL", "https://bus-sign.scottylabs.org"
).rstrip("/")
PREDICTIONS_PATH = "/predictions"
REQUEST_TIMEOUT_SECONDS = 10.0
LOCAL_TIMEZONE = "America/New_York"

KNOWN_STOPS: dict[str, KnownStop] = {
    "4407": {
        "name": "Forbes Ave & Morewood Ave (near Tepper Quad)",
        "direction": "inbound",
        "landmarks": ["Tepper", "Tepper Quad"],
        "typical_destinations": [
            "DOWNTOWN",
            "OAKLAND",
            "PITTSBURGH INTERNATIONAL AIRPORT",
        ],
    },
    "7117": {
        "name": "Forbes Ave & Morewood Ave (near CUC)",
        "direction": "outbound",
        "landmarks": ["CUC", "Cohon University Center"],
        "typical_destinations": [
            "MCKEESPORT",
            "BRADDOCK HILLS SHOPPING CENTER",
            "WATERFRONT",
            "FORBES HOSPITAL",
        ],
    },
}

# Interim baseline verified against PRT static GTFS feed Merged_Clever_2606_2.
# Replace this mapping with the generated GTFS/GIS index in the follow-up PR.
NEIGHBORHOOD_DESTINATION_AREAS: dict[str, NeighborhoodDestinationRule] = {
    "squirrel hill": {
        "stop_id": "7117",
        "areas": [
            {
                "key": "forbes_murray",
                "name": "Forbes Ave & Murray Ave",
                "target_stop_ids": ["7126"],
                "routes": ["61A", "61B", "61C", "61D"],
            },
            {
                "key": "wilkins_murray",
                "name": "Wilkins Ave & Murray Ave",
                "target_stop_ids": ["7681"],
                "routes": ["67", "69"],
            },
        ],
        "source": "PRT static GTFS feed Merged_Clever_2606_2",
    }
}

COVERAGE_NOTE = (
    "Coverage is limited to live predictions returned for two configured stops: "
    "stop 4407 — Forbes Ave & Morewood Ave near Tepper Quad, inbound toward "
    "Downtown/Oakland — and stop 7117 — Forbes Ave & Morewood Ave near CUC, "
    "outbound toward listed route destinations. Routes are taken dynamically "
    "from the backend and may vary."
)

CMU_PRT_SOURCE_URL = "https://www.cmu.edu/transportation/transport/prt.html"
CMU_PRT_RIDER_GUIDE = {
    "audience": "eligible CMU students",
    "benefit": (
        "Unlimited PRT bus, light rail, and incline rides with the current "
        "CMU monthly pass."
    ),
    "credential": "PRT Ready2Ride app with an @andrew.cmu.edu account",
    "steps": [
        "Install the PRT Ready2Ride app.",
        "Create or sign into an account using your @andrew.cmu.edu address; CMU aliases and personal email addresses do not receive the CMU pass.",
        "Find the Calendar Monthly Pass - CMU U-Pass in the app or Ticket Wallet.",
        "Activate the monthly pass and open its dynamic QR code before boarding.",
        "Hold the QR code over the vehicle validator until it confirms the pass is valid.",
    ],
    "important_notes": [
        "The physical CMU ID card is no longer the normal boarding credential.",
        "CMU users should not purchase tickets or add funds for rides covered by the CMU pass.",
        "Students without a usable mobile device should contact CMU Transportation about the card-based alternative.",
    ],
}
