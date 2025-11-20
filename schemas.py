"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogpost" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

class Userprofile(BaseModel):
    """
    User profile and baseline metrics
    Collection: "userprofile"
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    height_cm: Optional[float] = Field(None, gt=0, description="Height in centimeters")
    goal: Optional[str] = Field(None, description="Primary fitness goal")

class Workout(BaseModel):
    """
    Daily workout entries
    Collection: "workout"
    """
    user_email: str = Field(..., description="Email to link entries to a user")
    date: date = Field(..., description="Workout date")
    type: str = Field(..., description="Workout type, e.g., Strength, Cardio, Yoga")
    duration_min: float = Field(..., gt=0, description="Duration in minutes")
    intensity: Optional[str] = Field(None, description="Perceived intensity: Low/Med/High")
    notes: Optional[str] = Field(None, description="Freeform notes")
    calories: Optional[float] = Field(None, ge=0, description="Estimated calories burned")
    exercises: Optional[List[str]] = Field(default=None, description="List of exercises performed")

class Bodycomposition(BaseModel):
    """
    Body composition checkpoints
    Collection: "bodycomposition"
    """
    user_email: str = Field(..., description="Email to link entries to a user")
    date: date = Field(..., description="Measurement date")
    weight_kg: Optional[float] = Field(None, gt=0, description="Weight in kilograms")
    body_fat_pct: Optional[float] = Field(None, ge=0, le=100, description="Body fat percentage")
    waist_cm: Optional[float] = Field(None, gt=0, description="Waist circumference in cm")
    hips_cm: Optional[float] = Field(None, gt=0, description="Hips circumference in cm")
    chest_cm: Optional[float] = Field(None, gt=0, description="Chest circumference in cm")
