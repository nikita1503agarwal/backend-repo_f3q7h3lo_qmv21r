import os
from datetime import datetime, timedelta, date
from typing import List, Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from database import db, create_document, get_documents

app = FastAPI(title="Fitness Tracker API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------- Models ---------
class ProfileIn(BaseModel):
    name: str
    email: str
    height_cm: Optional[float] = Field(None, gt=0)
    goal: Optional[str] = None


class WorkoutIn(BaseModel):
    user_email: str
    date: date
    type: str
    duration_min: float = Field(..., gt=0)
    intensity: Optional[str] = None
    notes: Optional[str] = None
    calories: Optional[float] = Field(None, ge=0)
    exercises: Optional[List[str]] = None


class BodyCompIn(BaseModel):
    user_email: str
    date: date
    weight_kg: Optional[float] = Field(None, gt=0)
    body_fat_pct: Optional[float] = Field(None, ge=0, le=100)
    waist_cm: Optional[float] = Field(None, gt=0)
    hips_cm: Optional[float] = Field(None, gt=0)
    chest_cm: Optional[float] = Field(None, gt=0)


# --------- Utils ---------

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # Convert datetime/date to isoformat
    for k, v in list(d.items()):
        if isinstance(v, (datetime, date)):
            d[k] = v.isoformat()
    return d


# --------- Basic ---------
@app.get("/")
def read_root():
    return {"message": "Fitness Tracker API running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set",
        "database_name": "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set",
        "connection_status": "Not Connected",
        "collections": [],
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["connection_status"] = "Connected"
            try:
                response["collections"] = db.list_collection_names()[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️ Connected but Error: {str(e)[:80]}"
        else:
            response["database"] = "⚠️ Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:80]}"
    return response


# --------- Profiles ---------
@app.post("/api/profile")
def create_profile(profile: ProfileIn):
    pid = create_document("userprofile", profile)
    return {"id": pid}


@app.get("/api/profile")
def get_profile(email: str = Query(..., description="User email")):
    docs = get_documents("userprofile", {"email": email}, limit=1)
    if not docs:
        raise HTTPException(status_code=404, detail="Profile not found")
    return _serialize(docs[0])


# --------- Workouts ---------
@app.post("/api/workouts")
def add_workout(workout: WorkoutIn):
    wid = create_document("workout", workout)
    return {"id": wid}


@app.get("/api/workouts")
def list_workouts(
    user_email: str,
    start: Optional[date] = Query(None, description="Start date inclusive YYYY-MM-DD"),
    end: Optional[date] = Query(None, description="End date inclusive YYYY-MM-DD"),
    limit: Optional[int] = Query(50, ge=1, le=500),
):
    q: Dict[str, Any] = {"user_email": user_email}
    if start or end:
        rng: Dict[str, Any] = {}
        if start:
            rng["$gte"] = start
        if end:
            # inclusive end; store dates as date so <= end works
            rng["$lte"] = end
        q["date"] = rng
    docs = get_documents("workout", q, limit)
    # sort by date desc then created_at desc
    docs.sort(key=lambda d: (d.get("date"), d.get("created_at")), reverse=True)
    return [_serialize(d) for d in docs]


# --------- Body Composition ---------
@app.post("/api/bodycomp")
def add_bodycomp(measure: BodyCompIn):
    mid = create_document("bodycomposition", measure)
    return {"id": mid}


@app.get("/api/bodycomp")
def list_bodycomp(user_email: str, limit: int = Query(30, ge=1, le=365)):
    docs = get_documents("bodycomposition", {"user_email": user_email}, limit)
    docs.sort(key=lambda d: (d.get("date"), d.get("created_at")), reverse=True)
    return [_serialize(d) for d in docs]


# --------- Insights ---------
@app.get("/api/insights")
def insights(user_email: str, days: int = Query(30, ge=1, le=365)):
    today = date.today()
    start = today - timedelta(days=days - 1)
    wdocs = get_documents(
        "workout",
        {"user_email": user_email, "date": {"$gte": start, "$lte": today}},
        None,
    )
    # Aggregate
    total_sessions = len(wdocs)
    total_minutes = sum(float(w.get("duration_min", 0) or 0) for w in wdocs)
    avg_duration = (total_minutes / total_sessions) if total_sessions else 0
    by_day: Dict[str, float] = {}
    types: Dict[str, int] = {}
    streak = 0
    current_streak = 0

    # Build a set of days with workouts
    days_with = {str(w.get("date")) for w in wdocs}
    # compute current streak ending today
    d = today
    while str(d) in days_with:
        current_streak += 1
        d = d - timedelta(days=1)
    streak = current_streak

    for w in wdocs:
        ds = str(w.get("date"))
        by_day[ds] = by_day.get(ds, 0) + float(w.get("duration_min", 0) or 0)
        t = (w.get("type") or "Unknown").title()
        types[t] = types.get(t, 0) + 1

    # Simple suggestions
    suggestions = []
    if total_sessions < max(3, days // 4):
        suggestions.append("Increase frequency: aim for 3-4 sessions per week.")
    if avg_duration < 30 and total_sessions >= 3:
        suggestions.append("Bump average session length toward 30–45 minutes.")
    if types and max(types.values()) / (total_sessions or 1) > 0.7:
        suggestions.append("Balance your routine by mixing different workout types.")

    # Body comp trend (last and first)
    bdocs = get_documents(
        "bodycomposition", {"user_email": user_email}, None
    )
    bdocs.sort(key=lambda d: (d.get("date"), d.get("created_at")))
    weight_change = None
    if len(bdocs) >= 2:
        first = next((b for b in bdocs if b.get("weight_kg") is not None), None)
        last = next((b for b in reversed(bdocs) if b.get("weight_kg") is not None), None)
        if first and last:
            weight_change = float(last.get("weight_kg")) - float(first.get("weight_kg"))

    return {
        "totals": {
            "sessions": total_sessions,
            "minutes": total_minutes,
            "avg_duration": round(avg_duration, 1),
            "streak_days": streak,
        },
        "volume_by_day": by_day,
        "types": types,
        "suggestions": suggestions,
        "weight_change": weight_change,
    }


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
