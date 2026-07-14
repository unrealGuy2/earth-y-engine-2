from fastapi import APIRouter, HTTPException, BackgroundTasks, Header
from app.models.schemas import PassportCreateRequest, PassportStatusResponse
from app.core.database import supabase
from app.services.processing import process_passport_data

router = APIRouter()

@router.post("/generate", response_model=PassportStatusResponse)
async def create_passport(
    request: PassportCreateRequest, 
    background_tasks: BackgroundTasks,
    authorization: str = Header(None) # Extract the token from the frontend
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token")

    token = authorization.split(" ")[1]

    try:
        # 1. Verify the user using the token provided by the frontend
        auth_response = supabase.auth.get_user(token)
        user_id = auth_response.user.id

        # 2. Look up the user's Workspace ID
        profile_response = supabase.table("profiles").select("workspace_id").eq("id", user_id).single().execute()
        workspace_id = profile_response.data["workspace_id"]

        # 3. Format the Geometry for PostGIS (EWKT Format)
        if request.geometry.type == "Point":
            lon, lat = request.geometry.coordinates
            geom_wkt = f"SRID=4326;POINT({lon} {lat})"
        else:
            raise HTTPException(status_code=400, detail="Only Point geometry is supported in this phase.")

        # 4. Insert the new Passport record into the database
        passport_data = {
            "workspace_id": workspace_id,
            "created_by": user_id,
            "title": request.title,
            "geom": geom_wkt,
            "status": "pending"
        }

        insert_response = supabase.table("passports").insert(passport_data).execute()
        new_passport = insert_response.data[0]

        # 5. TRIGGER THE EARTH ENGINE BACKGROUND WORKER
        background_tasks.add_task(
            process_passport_data, 
            passport_id=new_passport["id"], 
            lon=lon, 
            lat=lat
        )

        return PassportStatusResponse(
            passport_id=new_passport["id"],
            status=new_passport["status"],
            message="Intelligence gathering initiated."
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))