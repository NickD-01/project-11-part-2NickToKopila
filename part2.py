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
# ideal temp: to calculate score
ideal_temperature = float(input(" your ideal temperature: "))
ideal_temperature = ideal_temperature.__round__(0)     #round to turn it into an approximate integer
ideal_temperature = int(ideal_temperature)         # float can't be used in range
five_point_temp = [x for x in range(ideal_temperature - 2 , ideal_temperature + 3)] # range(start,stop), excluding the last number
four_point_temp = [x for x in range(ideal_temperature - 3 , ideal_temperature + 4)]
three_point_temp = [x for x in range(ideal_temperature - 5, ideal_temperature + 6)]
two_point_temp = [x for x in range(ideal_temperature - 7 , ideal_temperature + 7)]
one_point_temp = [x for x in range(ideal_temperature - 10 , ideal_temperature + 10)]


print("optie.1 : Ik wil zeer weinig regen (<1mm).")
print("optie.2 : Ik wil minder dan 2mm per dag.")
print("optie.3 : Geen voorkeur.")
option = int(input("Kies een optie: "))




# Define locations with coordinates
# Dictionary with location names for their latitude and longitude coordinates

locations = {
    "Ankara, Turkije": (39.925533, 32.866287),
    "Athene, Griekenland": (37.9839412, 23.7283052),
    "La Valette, Malta": (35.884445, 14.506944),
    "Sardinië, Italië": (40.078072, 9.283447),
    "Sicilië, Italië": ( 37.587794, 14.155048),
    "Nicosia, Cyprus": (35.185566, 33.382275),
    "Mallorca, Spanje": (39.6952629, 3.0175712),
    "Lagos, Portugal": (37.129665, -8.669586),
    "Mauritius": (-20.20665, 57.6755),
    "Boekarest, Roemenië": (44.439663, 26.096306)
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
        timeslot_date = timeslot.get("dt_txt")[0:10] # doesn't include 10th letter

        if timeslot_date not in days_data:
            days_data[timeslot_date] = []
        days_data[timeslot_date].append(timeslot)

    return days_data


def extract_weather_info(days_data):
    # Extracts weather information for each day.

    weather_data = {}
    for day, daytimeslots in days_data.items():
        mintemp, maxtemp, rain = calculate_weather_metrics(daytimeslots)
        general_score = calculate_general_score((mintemp + maxtemp) / 2, rain)
        weather_data[day] = {"mintemp": mintemp, "maxtemp": maxtemp, "rain": round(rain, 2), "general_score": general_score}

    return weather_data


def calculate_weather_metrics(daytimeslots):
    # Calculates temperature metrics and total rainfall for each day.

    mintemps = []
    maxtemps = []
    rain = 0

    for timeslot in daytimeslots:
        mintemps.append(timeslot.get("main").get("temp_min"))
        maxtemps.append(timeslot.get("main").get("temp_max"))
        if timeslot.get("rain") is not None:
            rain += timeslot.get("rain").get("3h")

    mintemps.sort()
    maxtemps.sort()
    mintemp = round(mintemps[0], 2)
    maxtemp = round(maxtemps[-1], 2)

    return mintemp, maxtemp, rain


# Calculate General Score (../5) based on average temperature and rain that is present (<1mm or 2mm or no choice)
def calculate_general_score(average_temp, rain_present):
    #list import
    global five_point_temp
    global four_point_temp
    global three_point_temp
    global two_point_temp
    global one_point_temp
    global option

    average_temp = average_temp.__round__(0)
    average_temp = int(average_temp)


    if option == 1:
        if rain_present <= 1:
            rain_present = 4
        else:
            rain_present = 0
    elif option == 2:
        if rain_present <= 2:
            rain_present = 4
        else:
            rain_present = 0
    else:
        rain_present = 4

    if average_temp in five_point_temp:
        return 5
    elif average_temp in four_point_temp:
        return 4 + rain_present
    elif average_temp in three_point_temp:
        return 3 + rain_present
    elif average_temp in two_point_temp:
        return 2 + rain_present
    else:
        return 1 + rain_present


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
    score_ranking = {}
    # Create email content that displays the weekly weather updates for all different locations

    content = "Weekly Weather Update:\n\n"
    for location, weather_data in locations_weather.items():

        # variables for summarizing the week
        avg_temp_week = round(get_average_temperature(weather_data), 1)  # Round average temperature to one decimal
        total_rain_week = sum(data["rain"] for data in weather_data.values())

        # Calculate general score based on average temperature and rainfall
        general_score = calculate_general_score(avg_temp_week, total_rain_week)
        #nieuwe list maken om te rangschikken
        score_ranking[location] = {'general_score': general_score, 'avg_temp_week': avg_temp_week, 'total_rain_week': total_rain_week}
        score_ranking = dict(sorted(score_ranking.items(), key=lambda item: item[1]['general_score'], reverse=True))

    for location, data in score_ranking.items():
        content += f"Weather Update for {location}:\n"
        # round, because to calculate the score, the temp was converted to an int
        avg_temp_week = data['avg_temp_week'].__round__(0)
        total_rain_week = data['total_rain_week'].__round__(1)
        general_score = data['general_score']

        # content of the total rainfall
        if total_rain_week <= 1:
            total_rain_week = "zeer weinig regen (<= 1mm)"
        elif total_rain_week <= 2:
            total_rain_week = "gemiddeld regen (<= 2mm)"
        else:
            total_rain_week = "veel regen (> 2mm)"
        #just in case the general score is greater than 5
        if general_score >= 5:
            general_score = 5

        content += f"    Average Temperature of the Week: {avg_temp_week}°C\n"

        content += f"    Total rainfall of the Week: {total_rain_week}\n"
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
        message["From"] = "magarkopila22@gmail.com"  # replace with your own Gmail if you want it to work
        message["Subject"] = "🏖️️Weekly Weather Update☀️"

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
        print("An e-mail has been sent")
        service.users().drafts().send(userId="me", body=draft).execute()

    except HttpError as error:
        print(f"An error occurred: {error}")


if __name__ == "__main__":
    mail_sender()



