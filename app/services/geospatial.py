import ee
import logging
import requests
import base64
import os
from google.oauth2 import service_account

logger = logging.getLogger(__name__)

def initialize_earth_engine():
    """
    Initializes Google Earth Engine securely.
    Uses a Service Account in production (Render) and local credentials in development.
    """
    project_id = 'project-3a2b56f3-71b6-4f11-be4'
    key_path = "/etc/secrets/google-credentials.json"

    try:
        if os.path.exists(key_path):
            # Cloud Deployment Route: Uses the Service Account JSON
            credentials = service_account.Credentials.from_service_account_file(key_path)
            scoped_credentials = credentials.with_scopes(['https://www.googleapis.com/auth/earthengine'])
            ee.Initialize(credentials=scoped_credentials, project=project_id)
            logger.info("Earth Engine Initialized Securely via Cloud Service Account.")
        else:
            # Local Development Route: Uses your hidden laptop token
            ee.Initialize(project=project_id)
            logger.info("Earth Engine Initialized via Local Credentials.")
            
    except Exception as e:
        logger.error(f"CRITICAL: Failed to initialize Earth Engine: {e}")
        raise e

def get_terrain_intelligence(lon: float, lat: float) -> dict:
    """Extracts elevation and slope for a specific coordinate using SRTM DEM."""
    try:
        point = ee.Geometry.Point([lon, lat])
        dem = ee.Image('USGS/SRTMGL1_003')
        slope = ee.Terrain.slope(dem)

        elevation_data = dem.reduceRegion(reducer=ee.Reducer.mean(), geometry=point, scale=30).getInfo()
        slope_data = slope.reduceRegion(reducer=ee.Reducer.mean(), geometry=point, scale=30).getInfo()

        return {
            "elevation_meters": round(elevation_data.get('elevation', 0), 2),
            "slope_degrees": round(slope_data.get('slope', 0), 2)
        }
    except Exception as e:
        logger.error(f"Terrain query failed: {e}")
        return {"error": str(e)}

def get_land_intelligence(lon: float, lat: float, buffer_meters: int = 1000) -> dict:
    """Extracts land cover percentages within a 1km radius using ESA WorldCover 10m."""
    try:
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_meters)

        dataset = ee.ImageCollection("ESA/WorldCover/v200").first()
        landcover = dataset.select('Map')

        histogram = landcover.reduceRegion(
            reducer=ee.Reducer.frequencyHistogram(),
            geometry=roi,
            scale=10,
            maxPixels=1e8
        ).getInfo()

        raw_counts = histogram.get('Map', {})
        total_pixels = sum(raw_counts.values()) if raw_counts else 0

        if total_pixels == 0:
            return {"error": "No land cover data available for this region."}

        def calc_percent(classes):
            count = sum(raw_counts.get(str(c), 0) for c in classes)
            return round((count / total_pixels) * 100, 2)

        return {
            "forest_percent": calc_percent([10]),               
            "shrubland_percent": calc_percent([20, 30]),        
            "cropland_percent": calc_percent([40]),             
            "built_up_percent": calc_percent([50]),             
            "bare_ground_percent": calc_percent([60]),          
            "water_percent": calc_percent([80, 90, 95]),        
            "analysis_radius_meters": buffer_meters
        }
    except Exception as e:
        logger.error(f"Land intelligence query failed: {e}")
        return {"error": str(e)}

def get_water_intelligence(lon: float, lat: float, buffer_meters: int = 1000) -> dict:
    """
    Extracts historical water occurrence and distance to nearest surface water.
    Includes explicit unmasking to measure across land pixels.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_meters)

        jrc_dataset = ee.Image("JRC/GSW1_4/GlobalSurfaceWater")
        
        # --- METRIC 1: Historical Occurrence ---
        occurrence = jrc_dataset.select('occurrence')
        water_stats = occurrence.reduceRegion(
            reducer=ee.Reducer.max(),
            geometry=roi,
            scale=30,
            maxPixels=1e8
        ).getInfo()

        occurrence_val = water_stats.get('occurrence')
        final_occurrence = round(occurrence_val, 2) if occurrence_val is not None else 0.0

        # --- METRIC 2: Distance to Nearest Water ---
        water_binary = jrc_dataset.select('max_extent').unmask(0)
        search_kernel = ee.Kernel.euclidean(5000, 'meters')
        distance_img = water_binary.distance(search_kernel).rename('water_dist')
        
        dist_stats = distance_img.reduceRegion(
            reducer=ee.Reducer.first(),
            geometry=point,
            scale=30
        ).getInfo()
        
        dist_val = dist_stats.get('water_dist')
        distance_meters = round(dist_val, 2) if dist_val is not None else 5000.0

        return {
            "historical_water_occurrence_percent": final_occurrence,
            "distance_to_water_meters": distance_meters,
            "analysis_radius_meters": buffer_meters
        }

    except Exception as e:
        logger.error(f"Water intelligence query failed: {e}")
        return {"error": str(e)}

def get_environmental_history(lon: float, lat: float, buffer_meters: int = 1000) -> dict:
    """
    Phase 3: Environmental History Engine.
    Evaluates 10-year timeline trends for Vegetation (Sentinel-2), Urbanization (Dynamic World),
    and Surface Water Change (Dynamic World).
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        roi = point.buffer(buffer_meters)

        # Establish 10-Year Timeline Windows
        current_start, current_end = '2025-01-01', '2026-06-10'
        baseline_start, baseline_end = '2016-01-01', '2017-01-01'

        # ==========================================
        # 1. VEGETATION TREND ENGINE (Sentinel-2)
        # ==========================================
        s2 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')

        def mask_clouds_and_add_ndvi(image):
            qa = image.select('QA60')
            cloudBitMask = 1 << 10
            cirrusBitMask = 1 << 11
            mask = qa.bitwiseAnd(cloudBitMask).eq(0).And(qa.bitwiseAnd(cirrusBitMask).eq(0))
            ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
            return image.updateMask(mask).addBands(ndvi)

        baseline_img = s2.filterBounds(roi).filterDate(baseline_start, baseline_end).map(mask_clouds_and_add_ndvi).select('NDVI').median()
        current_img = s2.filterBounds(roi).filterDate(current_start, current_end).map(mask_clouds_and_add_ndvi).select('NDVI').median()

        baseline_stats = baseline_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=roi, scale=10, maxPixels=1e8).getInfo()
        current_stats = current_img.reduceRegion(reducer=ee.Reducer.mean(), geometry=roi, scale=10, maxPixels=1e8).getInfo()

        b_val = baseline_stats.get('NDVI')
        c_val = current_stats.get('NDVI')

        baseline_ndvi = round(b_val, 3) if b_val is not None else 0.0
        current_ndvi = round(c_val, 3) if c_val is not None else 0.0
        ndvi_delta = round(current_ndvi - baseline_ndvi, 3)
        
        if ndvi_delta <= -0.05:
            veg_trend = "Declining"
        elif ndvi_delta >= 0.05:
            veg_trend = "Improving"
        else:
            veg_trend = "Stable"

        # ==========================================
        # 2 & 3. DYNAMIC WORLD ENGINES (Urbanization & Water Change)
        # ==========================================
        dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')

        baseline_lc = dw.filterBounds(roi).filterDate(baseline_start, baseline_end).select('label').mode()
        current_lc = dw.filterBounds(roi).filterDate(current_start, current_end).select('label').mode()

        baseline_built = baseline_lc.eq(6).rename('built')
        current_built = current_lc.eq(6).rename('built')
        
        baseline_water = baseline_lc.eq(0).rename('water')
        current_water = current_lc.eq(0).rename('water')

        def get_binary_percent(binary_image, band_name):
            stats = binary_image.reduceRegion(
                reducer=ee.Reducer.mean(), 
                geometry=roi, 
                scale=10, 
                maxPixels=1e8
            ).getInfo()
            val = stats.get(band_name)
            return round((val * 100), 2) if val is not None else 0.0

        # Calculate Urbanization
        baseline_built_pct = get_binary_percent(baseline_built, 'built')
        current_built_pct = get_binary_percent(current_built, 'built')
        urban_growth_pct = round(current_built_pct - baseline_built_pct, 2)

        # Calculate Surface Water Change
        baseline_water_pct = get_binary_percent(baseline_water, 'water')
        current_water_pct = get_binary_percent(current_water, 'water')
        water_change_pct = round(current_water_pct - baseline_water_pct, 2)
        
        if water_change_pct <= -2.0:
            water_trend = "Losing Surface Water"
        elif water_change_pct >= 2.0:
            water_trend = "Expanding Surface Water"
        else:
            water_trend = "Stable Water Extent"

        return {
            "vegetation": {
                "baseline_ndvi_10yr": baseline_ndvi,
                "current_ndvi": current_ndvi,
                "ndvi_delta": ndvi_delta,
                "trend": veg_trend,
            },
            "urbanization": {
                "baseline_built_up_percent": baseline_built_pct,
                "current_built_up_percent": current_built_pct,
                "growth_percent": urban_growth_pct
            },
            "surface_water": {
                "baseline_water_percent": baseline_water_pct,
                "current_water_percent": current_water_pct,
                "change_percent": water_change_pct,
                "trend": water_trend
            },
            "analysis_radius_meters": buffer_meters,
            "timeline_window": "10-Year (2016-2026)"
        }

    except Exception as e:
        logger.error(f"Environmental history query failed: {e}")
        return {"error": str(e)}

def fetch_as_base64(url):
    """Helper function to bypass CORS by downloading the image in Python and converting to raw pixels."""
    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        b64 = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/png;base64,{b64}"
    except Exception as e:
        logger.error(f"Failed to encode image to base64: {e}")
        return url # Fallback to URL if it fails

def get_map_thumbnails(lon: float, lat: float, buffer_meters: int = 1000) -> dict:
    """
    Phase 6: Generates static maps and converts them directly to Base64.
    This bypasses ALL frontend CORS and PDF rendering bugs forever.
    """
    try:
        point = ee.Geometry.Point([lon, lat])
        region = point.buffer(buffer_meters).bounds()
        dimensions = '600x600' 

        # 1. True Color Context
        s2 = ee.ImageCollection('COPERNICUS/S2_HARMONIZED')\
            .filterBounds(region)\
            .filterDate('2024-01-01', '2026-06-10')\
            .sort('CLOUDY_PIXEL_PERCENTAGE')\
            .first().clip(region)
        tc_url = s2.visualize(bands=['B4', 'B3', 'B2'], min=0, max=3000, gamma=1.4)\
            .getThumbURL({'region': region, 'dimensions': dimensions, 'format': 'png'})

        # 2. Terrain
        dem = ee.Image('USGS/SRTMGL1_003').clip(region)
        dem_stats = dem.reduceRegion(reducer=ee.Reducer.minMax(), geometry=region, scale=30).getInfo()
        dem_min = dem_stats.get('elevation_min', 0)
        dem_max = dem_stats.get('elevation_max', 200)
        ter_url = dem.visualize(min=dem_min, max=dem_max, palette=['006600', '002200', 'fff700', 'ab7634', 'c4d0ff', 'ffffff'])\
            .getThumbURL({'region': region, 'dimensions': dimensions, 'format': 'png'})

        # 3. Land Cover
        dw = ee.ImageCollection('GOOGLE/DYNAMICWORLD/V1')\
            .filterBounds(region)\
            .filterDate('2025-01-01', '2026-06-10')\
            .select('label')\
            .first().clip(region)
        dw_palette = ['419BDF', '#397D49', '#88B053', '#7A87C6', '#E49635', '#DFC35A', '#C4281B', '#A59B8F', '#B39FE1']
        lc_url = dw.visualize(min=0, max=8, palette=dw_palette)\
            .getThumbURL({'region': region, 'dimensions': dimensions, 'format': 'png'})

        # 4. Surface Water
        jrc = ee.Image("JRC/GSW1_4/GlobalSurfaceWater").select('occurrence').clip(region)
        water_only = jrc.selfMask()
        background = ee.Image(0).clip(region).visualize(palette=['111111']) 
        water_layer = water_only.visualize(min=0, max=100, palette=['ffffff', 'ffbb22', '0000ff'])
        water_map = ee.ImageCollection([background, water_layer]).mosaic()
        wat_url = water_map.getThumbURL({'region': region, 'dimensions': dimensions, 'format': 'png'})

        # Convert the URLs to raw base64 data strings before saving to Supabase
        return {
            "true_color_url": fetch_as_base64(tc_url),
            "terrain_url": fetch_as_base64(ter_url),
            "land_cover_url": fetch_as_base64(lc_url),
            "water_url": fetch_as_base64(wat_url)
        }

    except Exception as e:
        logger.error(f"Map generation failed: {e}")
        return {"error": str(e)}