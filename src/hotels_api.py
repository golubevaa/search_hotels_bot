"""
All requests to Rapidapi. Processing of the received results.
"""

import requests
from math import ceil
from datetime import datetime
from typing import Tuple, Dict, List, Optional, Any, Union
from json import loads, JSONDecodeError
from re import sub
from src.bot_text import hotels_api_dict, hotels_rating
from bot_settings import headers


url = "https://hotels4.p.rapidapi.com/"


sort_order = {
    "/lowprice": "PRICE",
    "/highprice": "PRICE_HIGHEST_FIRST",
    "/bestdeal": "DISTANCE_FROM_LANDMARK"

}

endpoints = {
    "location": "locations/v2/search",
    "photo": "properties/get-hotel-photos",
    "hotels_list": "properties/list"

}


def request_to_hotels_api(_url: str, endpoint: str, querystring: Dict[str, str]) -> Optional[str]:
    """
    Makes all requests to rapidapi.

    :param _url: rapidapi url.
    :type _url: str
    :param endpoint: one of endpoints to get locations, list of hotels or hotels photo.
    :type endpoint: str
    :param querystring: request params.
    :type: Optional[str]
    :return: text of the response in cases if code of request is ok.
    :rtype: str
    """

    try:
        response = requests.request(method="GET",
                                    url=url + endpoint,
                                    headers=headers,
                                    params=querystring)
        if response.status_code == requests.codes.ok:
            return response.text
    except requests.exceptions.Timeout:
        return None


def get_locale(city: str) -> Optional[Dict[str, str]]:
    """
    Get supposed locations by city name.

    :param city: city name from user.
    :type city: str
    :return: dict["City name": "destinationId"]
    :rtype: Optional[Dict[str, str]]
    """

    supposed_locations = dict()
    querystring = {
        "query": city,
        "locale": "ru_RU",
        "currency": "USD"
    }
    response = request_to_hotels_api(_url=url,
                                     endpoint=endpoints["location"],
                                     querystring=querystring)
    if response:
        try:
            resp = loads(response)
            cities_dict = resp["suggestions"][0]["entities"]
            for city in cities_dict:
                destination = sub(r"<.*?>", "", city["caption"])
                destination_id = city["destinationId"]
                supposed_locations[destination] = destination_id
        except (JSONDecodeError, KeyError, TypeError):
            supposed_locations = None
    return supposed_locations


def find_city_center_distance(hotel: Dict) -> float:
    """
    Find a distance from hotel to city center.

    :param hotel:
    :type hotel: Dict
    :return: str
    """

    try:
        for landmark in hotel["landmarks"]:
            if landmark["label"] == "City center" or "Центр города":
                return float(landmark['distance'].split()[0].replace(",", "."))
    except KeyError:
        return hotels_api_dict["errors"]["distance"]


def find_timedelta(check_in: datetime, check_out: datetime) -> int:
    """
    Count booking days.

    :param check_in: check_in date
    :type check_in: datetime
    :param check_out: check_out date
    :type check_out: datetime
    :return: booking day
    :rtype: int
    """
    timedelta = check_out - check_in
    return timedelta.days


def calculate_price(hotel: Dict, timedelta: int) -> Tuple[str, str]:
    """
    Find price info in response

    :param hotel: dict
    :type hotel:
    :param timedelta: difference between check-in and check-out
    :type: timedelta: int
    :return: a tuple with price per day and total price
    :rtype: tuple[str, str]
    """
    try:
        price_per_night: int = ceil(hotel["ratePlan"]["price"]["exactCurrent"])
        full_price: str = str(price_per_night * timedelta) + "$"
        price_per_night: str = str(price_per_night) + "$"
    except KeyError:
        price_per_night: str = hotels_api_dict["errors"]["price"]
        full_price: str = hotels_api_dict["errors"]["price"]
    return price_per_night, full_price


def get_hotel_photos(hotel_id: int, num_of_photo: int) -> Optional[List[str]]:
    """
    Finds hotel photos links.

    :param hotel_id: id of hotel
    :type hotel_id: int
    :param num_of_photo: count of photo
    :type num_of_photo: int
    :return: List with photos urls.
    :rtype: Optional[List[str]]
    """

    querystring = {"id": str(hotel_id)}
    response = request_to_hotels_api(_url=url,
                                     endpoint=endpoints["photo"],
                                     querystring=querystring)
    if response:
        try:
            resp = loads(response)
            img_data_list = []
            for photo_group in resp["roomImages"] + resp["hotelImages"]:
                if photo_group.get("images"):
                    for image in photo_group["images"]:
                        img_data_list.append(image["baseUrl"].format(size="z"))
                        if len(img_data_list) == num_of_photo:
                            return img_data_list
                else:
                    img_data_list.append(photo_group["baseUrl"].format(size="z"))
                    if len(img_data_list) == num_of_photo:
                        return img_data_list
        except (JSONDecodeError, KeyError):
            return


def sort_hotels(command: str, hotels: Dict[Any, Any], distance: Optional[float] = None) -> Optional[List[Dict]]:
    """
    Sorts hotels according to command.

    :param command: user command
    :type command: str
    :param hotels: dict with hotels from rapidapi
    :type hotels: Dict[Any, Any]
    :param distance: max distance from city center.
    :type distance: Optional[float]
    :return: list with sorted hotels dict.
    :rtype: Optional[List[Dict]]
    """

    if command == '/highprice':
        reverse = True
    else:
        reverse = False

    hotels: List[dict] = sorted(hotels, key=lambda hotel: sort_price(hotel), reverse=reverse)

    if command == '/bestdeal':
        distance_filter = list(filter(lambda hotel: find_city_center_distance(hotel) <= distance, hotels))
        hotels: List[dict] = sorted(distance_filter, key=lambda hotel: find_city_center_distance(hotel))

    return hotels


def sort_price(hotel: Dict[Any, Any]) -> Union[float, int]:
    """
    Method is used to sort hotels by price.
    Finds price in hotel dict.

    :param hotel: Dict with hotel info.
    :type hotel: Dict[Any, Any]
    :return: price if price is found else 0.
    :rtype: float
    """

    try:
        return hotel['ratePlan']['price']['exactCurrent']
    except KeyError:
        return 0


def get_hotels_dict(destination_id: str, hotel_count: str, check_in: datetime,
                    check_out: datetime, adults: Dict[str, str], command: str,
                    min_price: Optional[str] = "", max_price: Optional[str] = "",
                    children: Optional[Dict[str, str]] = None,
                    distance: Optional[float] = None) -> Tuple[Optional[Dict[int, Dict[str, str]]], Optional[float]]:
    """
    Creates dict with hotels info.

    :param destination_id: id of location
    :type destination_id: str
    :param hotel_count: number of hotels needed to be found
    :type hotel_count: str
    :param check_in: check-in date
    :type check_in: datetime
    :param check_out: check-out date
    :type check_out: datetime
    :param adults: info about adults in rooms
    :type adults: Dict[str, str]
    :param command: user's command for searching hotels.
    :type command: str
    :param min_price: min cost per night in /bestdeal scenario
    :type min_price: Optional[str]
    :param max_price: max cost per night in /bestdeal scenario
    :type max_price: Optional[str]
    :param children: info about children in room
    :type children: Optional[Dict[str, str]]
    :param distance: max distance from hotel to city center (/bestdeal scenario)
    :type distance: Optional[float]
    :return: dict with hotels info according to filters, might be empty. In these cases
        returns min distance from hotel to city center (/bestdeal scenario).
    :rtype: Tuple[Optional[Dict[int, Dict[str, str]]], Optional[float]]
    """
    summary = dict()
    min_distance = None
    querystring = {
        "destinationId": destination_id,
        "pageNumber": "1",
        "pageSize": "25",
        "checkIn": check_in.strftime("%Y-%m-%d"),
        "checkOut": check_out.strftime("%Y-%m-%d"),
        "sortOrder": sort_order[command],
        "locale": "ru_RU",
        "currency": "USD"
    }
    querystring.update(adults)
    if children:
        querystring.update(children)
    if command == "/bestdeal":
        querystring.update({
            "priceMin": str(int(min_price)),
            "priceMax": str(int(max_price)),
        })
    response = request_to_hotels_api(_url=url,
                                     endpoint=endpoints["hotels_list"],
                                     querystring=querystring)
    if response:
        try:
            resp = loads(response)
        except JSONDecodeError:
            pass
        else:
            sorted_hotels = sort_hotels(command=command,
                                        hotels=resp["data"]["body"]["searchResults"]["results"],
                                        distance=distance)
            if sorted_hotels:
                if len(sorted_hotels) > int(hotel_count):
                    sorted_hotels = sorted_hotels[:int(hotel_count)]

                timedelta = find_timedelta(check_in=check_in,
                                           check_out=check_out)
                for hotel in sorted_hotels:
                    summary.update(format_hotel_info(hotel=hotel,
                                                     timedelta=timedelta))
            else:
                min_distance = min([find_city_center_distance(hotel) for hotel in
                                    resp["data"]["body"]["searchResults"]["results"]])
    return summary, min_distance


def get_rating(hotel: Dict[Any, Any]) -> str:
    """
    Finds hotel rating and creates string for it.

    :param hotel: hotel dict
    :type: Dict[Any, Any]
    :return: string with rating.
    :rtype: str
    """
    rating = ""
    try:
        rating_val = ceil(hotel["starRating"])
        rating = hotels_rating["star"] * rating_val
    except KeyError:
        rating = hotels_rating["unknown"]
    return rating


def format_hotel_info(hotel: Dict[Any, Any], timedelta: int) -> Dict[int, Dict[str, str]]:
    """
    Creates dict with info for messages with booking info.

    :param hotel: hotel dict from rapidapi
    :type hotel: Dict[Any, Any]
    :param timedelta: booking days
    :type timedelta: int
    :return: dict with info for booking messages
    :rtype: Dict[int, Dict[str, str]]
    """

    try:
        location = hotel["address"]["locality"] + ", " + hotel["address"]["streetAddress"]
    except KeyError:
        location = hotel["address"]["locality"]
    city_center_distance = find_city_center_distance(hotel)
    rating = get_rating(hotel)
    price_per_night, full_price = calculate_price(hotel=hotel,
                                                  timedelta=timedelta)
    return {
        hotel["id"]: {
            hotels_api_dict["main_message"]["hotel"]: hotel["name"],
            hotels_api_dict["main_message"]["rating"]: rating,
            hotels_api_dict["main_message"]["address"]: location,
            hotels_api_dict["main_message"]["center"]: str(city_center_distance) + " км",
            hotels_api_dict["main_message"]["per_night"]: price_per_night,
            hotels_api_dict["main_message"]["total_sum"]: full_price
        }
    }

