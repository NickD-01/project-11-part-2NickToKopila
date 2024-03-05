import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import base64
from email.message import EmailMessage
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import requests
import datetime

# Modify scope? Delete token.json
# Scopes are required for accessing Gmail API
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
                "https://www.googleapis.com/auth/gmail.compose",
                "https://www.googleapis.com/auth/gmail.send"]

# OpenWeather API key and API usage
# API key
Openweather_API_KEY = "55324226498c187fb750c027464f6da7"
# get weather data from OpenWeatherMap API
Openweather_api_getter = "https://api.openweathermap.org/data/2.5/forecast"

# Send mail to a custom email address
address = input("E-mail you wish to address: ")

# Define locations with coordinates
# Dictionary with location names for their latitude and longitude coordinates
locations = {
    "Les Trois Vallées": (45.3356, 6.5890),
    "Sölden": (46.9701, 11.0078),
    "Chamonix Mont Blanc": (45.9237, 6.8694),
    "Val di Fassa": (46.4265, 11.7684),
    "Salzburger Sportwelt": (47.3642, 13.4639),
    "Alpenarena Films-Laax-Falera": (46.8315, 9.2663),
    "Kitzsteinhorn Kaprun": (47.1824, 12.6912),
    "Ski Altberg": (47.43346, 8.42053),
    "Espace Killy": (45.4481, 6.9806),
    "Špindlerův Mlýn": (50.7296, 15.6075)
}


# Get weather data for a specific location using the coordinates
def get_weather_data(api_key, lat, lon):
    # Gets weather data from the API for the given latitude and longitude.
    # Returns Weather data for that location.

    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    response = requests.get(Openweather_api_getter, params=params)
    finalresponse = response.json()

    timeslots = get_hourly_forecast(finalresponse)
    today_date = get_current_date()
    days_data = group_by_day(timeslots)
    weather_data = extract_weather_info(days_data)

    return weather_data


def get_hourly_forecast(response):
    # Extracts hourly forecast data from the API response.

    return response.get("list")


def get_current_date():
    # Returns today's date in the format YYYY-MM-DD.

    return datetime.datetime.now().strftime("%Y-%m-%d")


def group_by_day(timeslots):
    # Groups hourly forecast data by day.

    days_data = {}
    for timeslot in timeslots:
        timeslot_date = timeslot.get("dt_txt")[0:10]
        if timeslot_date not in days_data:
            days_data[timeslot_date] = []
        days_data[timeslot_date].append(timeslot)

    return days_data


def extract_weather_info(days_data):
    # Extracts weather information for each day.

    weather_data = {}
    for day, daytimeslots in days_data.items():
        mintemp, maxtemp, snow = calculate_weather_metrics(daytimeslots)
        general_score = calculate_general_score((mintemp + maxtemp) / 2, snow)
        weather_data[day] = {"mintemp": mintemp, "maxtemp": maxtemp, "snow": round(snow, 2), "general_score": general_score}

    return weather_data


def calculate_weather_metrics(daytimeslots):
    # Calculates temperature metrics and total snowfall for each day.

    mintemps = []
    maxtemps = []
    snow = 0

    for timeslot in daytimeslots:
        mintemps.append(timeslot.get("main").get("temp_min"))
        maxtemps.append(timeslot.get("main").get("temp_max"))
        if timeslot.get("snow") is not None:
            snow += timeslot.get("snow").get("3h")

    mintemps.sort()
    maxtemps.sort()
    mintemp = round(mintemps[0], 2)
    maxtemp = round(maxtemps[-1], 2)

    return mintemp, maxtemp, snow


# Calculate General Score (../5) based on average temperature and snow that is present (5 cm or more)
def calculate_general_score(average_temp, snow_present):

    if snow_present >= 5:  # Check if snowfall is 5 cm or more
        snow_present = 1
    else:
        snow_present = 0

    if average_temp < 0:
        return 5
    elif 0 <= average_temp < 5:
        return 4 + snow_present
    elif 5 <= average_temp < 10:
        return 3 + snow_present
    else:
        return 1 + snow_present


# Get average temperature for the locations
def get_average_temperature(weather_data):

    total_temp = 0
    count = 0
    for day, data in weather_data.items():
        total_temp += (data["mintemp"] + data["maxtemp"]) / 2
        count += 1
    return total_temp / count if count else 0


# All mail content + "styling" of the mail
def create_email_content(locations_weather):
    # Create email content that displays the weekly weather updates for all different locations

    content = "Weekly Weather Update:\n\n"
    for location, weather_data in locations_weather.items():
        content += f"Weather Update for {location}:\n"

        # variables for summarizing the week
        avg_temp_week = round(get_average_temperature(weather_data), 1)  # Round average temperature to one decimal
        total_snow_week = sum(data["snow"] for data in weather_data.values())

        # Calculate general score based on average temperature and snowfall
        general_score = calculate_general_score(avg_temp_week, total_snow_week)

        content += f"    Average Temperature of the Week: {avg_temp_week}°C\n"
        content += f"    Total Snowfall of the Week: {round(total_snow_week / 10, 1)}cm\n"
        content += f"    General Score: {general_score}/5\n\n"
    content += "Thank you for using UltimateWeatherUpdates!"
    return content


def mail_sender():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", GMAIL_SCOPES)
    # If there are no (valid) credentials, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", GMAIL_SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials (to token.json) for next time
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        # Call Gmail API
        service = build("gmail", "v1", credentials=creds)

        locations_weather = {}

        for location, (lat, lon) in locations.items():
            # Get weather data for each location
            weather_data = get_weather_data(Openweather_API_KEY, lat, lon)
            # Add General score to each day's weather data
            locations_weather[location] = weather_data

        # Create email content with weather data
        email_content = create_email_content(locations_weather)
        message = EmailMessage()
        message.set_content(email_content)
        message["To"] = address
        message["From"] = "nick.decoster07@gmail.com"  # replace with your own Gmail if you want it to work
        message["Subject"] = "⛷️Weekly Weather Update🏂"

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()

        create_message = {"message": {"raw": encoded_message}}

        # Create and send draft email
        draft = (
            service.users()
            .drafts()
            .create(userId="me", body=create_message)
            .execute()
        )
        print(f'Draft id: {draft["id"]}\nDraft message: {draft["message"]}')
        service.users().drafts().send(userId="me", body=draft).execute()

    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    mail_sender()
