"""Météo et prévisions via l'API OpenWeatherMap."""
import os

import httpx

from utils import format_forecast, summarize_forecast

API_URL = "https://api.openweathermap.org/data/2.5/{endpoint}"


class WeatherError(Exception):
    """Erreur lisible à afficher directement à l'utilisateur."""


async def _request(endpoint: str, city: str) -> dict:
    api_key = os.getenv("OPENWEATHER_API_KEY")
    if not api_key:
        raise WeatherError("La météo n'est pas configurée (clé OPENWEATHER_API_KEY manquante).")

    params = {"q": city, "appid": api_key, "units": "metric", "lang": "fr"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(API_URL.format(endpoint=endpoint), params=params)
    except httpx.HTTPError:
        raise WeatherError("Impossible de joindre le service météo, réessaie plus tard.")

    if response.status_code == 404:
        raise WeatherError(f"Ville introuvable : {city}")
    if response.status_code == 401:
        raise WeatherError("Clé API météo invalide ou pas encore activée.")
    if response.status_code != 200:
        raise WeatherError("Le service météo a renvoyé une erreur, réessaie plus tard.")
    return response.json()


async def get_weather(city: str) -> str:
    data = await _request("weather", city)
    description = data["weather"][0]["description"].capitalize()
    temp = data["main"]["temp"]
    feels = data["main"]["feels_like"]
    humidity = data["main"]["humidity"]
    wind = data["wind"]["speed"] * 3.6  # m/s -> km/h

    return (
        f"🌍 {data['name']}, {data['sys'].get('country', '')}\n"
        f"{description}\n"
        f"🌡️ {temp:.0f}°C (ressenti {feels:.0f}°C)\n"
        f"💧 Humidité : {humidity}%\n"
        f"💨 Vent : {wind:.0f} km/h"
    )


async def get_forecast(city: str) -> str:
    data = await _request("forecast", city)
    info = data["city"]
    return format_forecast(info["name"], info.get("country", ""), summarize_forecast(data))
