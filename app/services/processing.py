import logging
from app.core.database import supabase
from app.services.geospatial import (
    get_terrain_intelligence, 
    get_land_intelligence, 
    get_water_intelligence,
    get_environmental_history,
    get_map_thumbnails
)
from app.services.risk import calculate_site_risk
from app.services.executive import generate_executive_summary

logger = logging.getLogger(__name__)

def process_passport_data(passport_id: str, lon: float, lat: float):
    """
    Background worker that runs all active intelligence engines, risk scoring, and map generation.
    """
    try:
        supabase.table("passports").update({"status": "processing"}).eq("id", passport_id).execute()
        logger.info(f"Starting Earth Engine analysis for Passport {passport_id}")

        # --- RUN EXTRACTION ENGINES (Phases 1-3) ---
        terrain_payload = get_terrain_intelligence(lon, lat)
        land_payload = get_land_intelligence(lon, lat)
        water_payload = get_water_intelligence(lon, lat)
        history_payload = get_environmental_history(lon, lat)

        # --- RUN MAP GENERATION ENGINE (Phase 6) ---
        map_payload = get_map_thumbnails(lon, lat)

        if "error" in terrain_payload or "error" in land_payload or "error" in water_payload or "error" in history_payload or "error" in map_payload:
            raise Exception("One or more extraction engines failed to return data.")

        # --- RUN SYNTHESIS & EXECUTIVE ENGINES (Phases 4-5) ---
        risk_payload = calculate_site_risk(terrain_payload, land_payload, water_payload, history_payload)
        
        if "error" in risk_payload:
            raise Exception("Risk synthesis engine failed.")
            
        executive_payload = generate_executive_summary(terrain_payload, water_payload, history_payload, risk_payload)

        # --- SAVE TO DATABASE ---
        supabase.table("passports").update({
            "status": "completed",
            "terrain_data": terrain_payload,
            "land_data": land_payload,
            "water_data": water_payload,
            "history_data": history_payload,
            "risk_data": risk_payload,
            "executive_data": executive_payload,
            "map_data": map_payload
        }).eq("id", passport_id).execute()
        
        logger.info(f"Successfully completed Passport {passport_id}")

    except Exception as e:
        logger.error(f"Failed to process passport {passport_id}: {e}")
        supabase.table("passports").update({"status": "failed"}).eq("id", passport_id).execute()