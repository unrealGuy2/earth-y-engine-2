from pydantic import BaseModel, Field
from typing import List, Optional, Union

# Represents a single coordinate drop
class PointGeometry(BaseModel):
    type: str = "Point"
    coordinates: List[float]  # [longitude, latitude]

# Represents a drawn site boundary
class PolygonGeometry(BaseModel):
    type: str = "Polygon"
    coordinates: List[List[List[float]]]  # GeoJSON standard format

# The payload the Next.js frontend will send us
class PassportCreateRequest(BaseModel):
    title: str = Field(..., description="The user-defined name of the site")
    address: Optional[str] = None
    geometry: Union[PointGeometry, PolygonGeometry] = Field(
        ..., 
        description="Must be either a Point or a Polygon"
    )

# The immediate response we send back to the frontend
class PassportStatusResponse(BaseModel):
    passport_id: str
    status: str
    message: str