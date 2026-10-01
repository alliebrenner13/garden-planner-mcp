from __future__ import annotations

from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from garden_planner import services

STATIC = Path(__file__).resolve().parent / "static"


async def index(_request: Request) -> FileResponse:
    return FileResponse(STATIC / "index.html")


async def api_garden(request: Request) -> JSONResponse:
    if request.method == "PATCH":
        payload = await request.json()
        result = services.update_plot(payload)
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)
    return JSONResponse(services.garden_snapshot())


async def api_plants(_request: Request) -> JSONResponse:
    return JSONResponse(services.catalog())


async def api_plantings(request: Request) -> JSONResponse:
    if request.method == "POST":
        payload = await request.json()
        result = services.add_planting(payload)
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)
    status = request.query_params.get("status")
    plant_name = request.query_params.get("plant_name")
    return JSONResponse(services.list_log(status=status, plant_name=plant_name))


async def api_planting(request: Request) -> JSONResponse:
    planting_id = int(request.path_params["planting_id"])
    payload = await request.json()
    result = services.patch_planting(planting_id, payload)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


async def api_forecast(request: Request) -> JSONResponse:
    days = int(request.query_params.get("days") or 7)
    result = services.forecast(days)
    return JSONResponse(result, status_code=200 if result.get("ok") else 502)


async def api_frost(request: Request) -> JSONResponse:
    days = int(request.query_params.get("days") or 7)
    result = services.frost_report(
        forecast_days=days,
        start_date=request.query_params.get("start_date"),
        end_date=request.query_params.get("end_date"),
    )
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


async def api_window(request: Request) -> JSONResponse:
    plant = request.query_params.get("plant") or ""
    year_raw = request.query_params.get("year")
    year = int(year_raw) if year_raw else None
    result = services.window(plant, year)
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


async def api_setup(request: Request) -> JSONResponse:
    if request.method == "POST":
        payload = await request.json()
        result = services.complete_setup(payload)
        return JSONResponse(result, status_code=200 if result.get("ok") else 400)
    return JSONResponse(services.setup_status())


async def api_places(request: Request) -> JSONResponse:
    result = services.search_places(request.query_params.get("q") or "")
    return JSONResponse(result, status_code=200 if result.get("ok") else 400)


app = Starlette(
    routes=[
        Route("/", index),
        Route("/api/garden", api_garden, methods=["GET", "PATCH"]),
        Route("/api/plants", api_plants),
        Route("/api/plantings", api_plantings, methods=["GET", "POST"]),
        Route("/api/plantings/{planting_id:int}", api_planting, methods=["PATCH"]),
        Route("/api/forecast", api_forecast),
        Route("/api/frost", api_frost),
        Route("/api/window", api_window),
        Route("/api/setup", api_setup, methods=["GET", "POST"]),
        Route("/api/places", api_places),
        Mount("/static", StaticFiles(directory=STATIC), name="static"),
    ]
)


def main() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")


if __name__ == "__main__":
    main()
