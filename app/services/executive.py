import logging

logger = logging.getLogger(__name__)

def generate_executive_summary(terrain_data: dict, water_data: dict, history_data: dict, risk_data: dict) -> dict:
    """
    Phase 5: Generates a consultant-facing Red/Amber/Green executive summary based on raw metrics.
    """
    try:
        # 1. Determine Overall RAG Status
        score = risk_data.get("risk_score", 0)
        if score >= 50:
            overall_status = "RED"
            recommendation = "Immediate field verification and comprehensive environmental site assessment (ESA) are strongly recommended."
        elif score >= 25:
            overall_status = "AMBER"
            recommendation = "Targeted field verification is recommended to assess identified vulnerabilities."
        else:
            overall_status = "GREEN"
            recommendation = "Standard due diligence is sufficient. No anomalous environmental risks detected."

        # 2. Construct the Executive Insight Paragraph
        classification = risk_data.get("risk_classification", "UNKNOWN").lower()
        factors = risk_data.get("critical_factors", [])

        if factors:
            # Grab the top two critical factors to build a natural sentence
            factor_text = factors[0].lower().rstrip('.')
            if len(factors) > 1:
                factor_text += f" and {factors[1].lower().rstrip('.')}"
            insight_text = f"The site exhibits {classification} susceptibility primarily due to {factor_text}. {recommendation}"
        else:
            insight_text = f"The site exhibits {classification} susceptibility. {recommendation}"

        # 3. Generate Module-Level RAG Summaries
        terrain_slope = terrain_data.get("slope_degrees", 0)
        water_prox = water_data.get("distance_to_water_meters", 5000)
        water_flood = water_data.get("historical_water_occurrence_percent", 0)

        return {
            "overall_status": overall_status,
            "executive_insight": insight_text,
            "modules": {
                "terrain": {
                    "finding": f"Terrain is characterized by maximum slopes of {terrain_slope}°.",
                    "status": "RED" if terrain_slope > 20 else ("AMBER" if terrain_slope > 12 else "GREEN")
                },
                "water": {
                    "finding": f"Proximity to surface water is {water_prox}m with {water_flood}% historical flood occurrence.",
                    "status": "RED" if (water_prox < 500 or water_flood > 10) else ("AMBER" if (water_prox < 1000 or water_flood > 0) else "GREEN")
                },
                "history": {
                    "finding": f"10-Year vegetation trend is {history_data.get('vegetation', {}).get('trend', 'Stable')}.",
                    "status": "RED" if history_data.get('vegetation', {}).get('trend') == "Declining" else "GREEN"
                }
            }
        }

    except Exception as e:
        logger.error(f"Executive summary generation failed: {e}")
        return {"error": str(e)}