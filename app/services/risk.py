import logging

logger = logging.getLogger(__name__)

def calculate_site_risk(terrain_data: dict, land_data: dict, water_data: dict, history_data: dict) -> dict:
    """
    Phase 4: Synthesizes extracted geospatial metrics into a definitive Environmental Risk Score.
    """
    try:
        score = 0
        risk_factors = []

        # 1. HYDROLOGICAL RISK (Max 40 Points)
        proximity = water_data.get("distance_to_water_meters", 5000)
        flood_history = water_data.get("historical_water_occurrence_percent", 0)
        
        if proximity < 500:
            score += 20
            risk_factors.append(f"High proximity to surface water ({proximity}m).")
        elif proximity < 1000:
            score += 10
            risk_factors.append(f"Moderate proximity to surface water ({proximity}m).")
            
        if flood_history > 10:
            score += 20
            risk_factors.append(f"Historical flooding detected ({flood_history}% occurrence).")
        elif flood_history > 0:
            score += 10
            risk_factors.append("Trace historical surface water detected.")

        # 2. TOPOGRAPHICAL RISK (Max 30 Points)
        elevation = terrain_data.get("elevation_meters", 100)
        slope = terrain_data.get("slope_degrees", 0)

        if elevation < 5:
            score += 15
            risk_factors.append(f"Critical low elevation ({elevation}m) - high inundation vulnerability.")
        elif elevation < 10:
            score += 5
            risk_factors.append(f"Low elevation ({elevation}m).")

        if slope > 20:
            score += 15
            risk_factors.append(f"Steep terrain ({slope}°) - extreme landslide/erosion risk.")
        elif slope > 12:
            score += 10
            risk_factors.append(f"Moderate slope incline ({slope}°).")

        # 3. ENVIRONMENTAL DEGRADATION (Max 30 Points)
        veg_trend = history_data.get("vegetation", {}).get("trend", "Stable")
        urban_growth = history_data.get("urbanization", {}).get("growth_percent", 0)

        if veg_trend == "Declining":
            score += 15
            risk_factors.append("Long-term vegetation decline detected.")
            
        if urban_growth > 5.0:
            score += 15
            risk_factors.append(f"Rapid urbanization ({urban_growth}% growth) increasing surface runoff.")
        elif urban_growth > 2.0:
            score += 5
            risk_factors.append("Moderate urbanization growth detected.")

        # DETERMINE FINAL CLASSIFICATION
        if score < 25:
            classification = "LOW RISK"
        elif score < 50:
            classification = "MODERATE RISK"
        elif score < 75:
            classification = "HIGH RISK"
        else:
            classification = "SEVERE RISK"

        return {
            "risk_score": score,
            "risk_classification": classification,
            "critical_factors": risk_factors
        }

    except Exception as e:
        logger.error(f"Risk engine synthesis failed: {e}")
        return {"error": str(e)}