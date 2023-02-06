"""
UserRequest and Scenario keyboard classes.
"""

from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from typing import Dict, List, Optional, Union, Any, Tuple
from abc import ABC
from datetime import date
from re import search
from db.userstates_db import *
from src.bot_text import current_choice, kb_text


class UserRequest:
    """
    Class describing the user

    Args:
        :user_id (str):   user_id of telegram user. Get from user.
        :destination_id (str):   Location code to find the hotels. Get from rapidapi.
        :start_search Optional[Message]:    Message with list of supposed cities.
        :start_search_pool List[Optional[int]]:    list with id's of messages (except commands) sent by user
            after list of supposed cities was sent. The messages will be deleted
            after supposed location will be changed.
        :cur_step: Optional[Message]:   Message instance related to current step in scenario.
        :location_name (str):   location name to show it to user
            instead location code. Get from rapidapi.

        :hotel_count (str):   number of hotels in current request. Get from user.
        :check_in (date):   check-in date. Get from user.
        :check_out (date):   check-out date. Get from user.
        :adults (list[int]):   info about count of adults in rooms. Index is a room,
            value is a number of adults. Get from user.

        :_adults (dict[str, str]):   dict "room": "adults in room".
            Creates from adults before start the search.

        :children (dict[str, list[int]):  dict "room": [ages of children in room]. Get from user.
        :memory (dict[any]):   storage to save text messages and  keyboard
            markup for current query. Get from user.

        :command (str):   current user's command for search. Get from user.
        :main_message int:   id of the message with all info about location,
            number of hotels, check-in and check-out dates. Get from user.

        :main_rooms_message (int):   id of the message with all info about
            rooms in current query. Get from user.
        :need_photo (Union[bool, int]):   False if no photo in response is needed.
            number of photos (from 1 to 10) if photos will be existed in response.
        :min_price (Optional[float]): min price per night.
        :max_price (Optional[float]): max price per night.
        :distance (Optional[float]): max distance from hotel to city center.
        :stage (str): current user stage (see stages at src.bot_stages.py)

    """

    def __init__(self, user_id):

        self.user_id: int = user_id
        self._start_search: Optional[Message] = None
        self.start_search_pool: List[Optional[int]] = []
        self._cur_step: Optional[Message] = None
        self.destination_id: Optional[str] = ""
        self.location_name: Optional[str] = ""
        self.hotel_count: Optional[str] = ""
        self.check_in: Optional[date] = None
        self.check_out: Optional[date] = None
        self.total_room: int = 0
        self._adults: Dict[Optional[str, str]] = dict()
        self.adults: List[Optional[int]] = []
        self.children: Dict[Optional[str, Union[List[int], str]]] = dict()
        self.guest_cycle: Dict[int, bool] = {i: False for i in range(8)}
        self.memory: Dict[str, Any] = \
            {
            "location": dict(),
            "hotel_count": dict(),
            "dates": {
                "check_in": {},
                "check_out": {}
            },
            "rooms": dict(),
            "finish": ""
        }
        self.command: str = ""
        self.main_message: Optional[int] = None
        self.main_rooms_message: Optional[int] = None
        self.need_photo: Union[bool, int] = False
        self.min_price: Optional[float] = None
        self.max_price: Optional[float] = None
        self.distance: Optional[float] = None
        self.stage: str = "start"

    @classmethod
    def get_user(cls, user_id: int) -> 'UserRequest':
        """
        Returns an UserRequest instance with id = user_id.

        :param user_id: user_id of UserRequest instance to find in users dict.
        :type user_id: int
        :return: UserRequest instance with id as user_id.
        :rtype: UserRequest
        """

        user_in_db = get_user_state_from_db(user_id=user_id)
        if user_in_db:
            return user_in_db
        return UserRequest(user_id=user_id)

    @property
    def start_search(self):
        """ _start_search getter """

        return self._start_search

    @start_search.setter
    def start_search(self, step):
        """ _start_search setter """

        self._start_search = step
        update_user_state(self)

    @property
    def cur_step(self):
        """ _cur_step getter """

        return self._cur_step

    @cur_step.setter
    def cur_step(self, step):
        """ _cur_step setter """

        self._cur_step = step
        update_user_state(self)

    def add_child(self, age: int, room: int) -> None:
        """
        Adds a child using his age to passed room.

        :param age: age of child
        :type age: int
        :param room: room to add the child (starts from 0).
        :type: int
        :return:
        """

        self.children[f"children{room + 1}"].append(age)

    def remove_children(self, room) -> None:
        """
        Removes all children from passed room.

        :param room: room to remove children (starts from 0).
        :type: int
        :return: None
        """

        self.children[f"children{room + 1}"] = []

    def count_child(self) -> int:
        """
        Method to count all children in all rooms for current query.

        :return: number if children in all rooms in the query.
        :rtype: int
        """

        _sum = 0
        for value in self.children.values():
            if value:
                _sum += len(value)
        return _sum

    def define_need_photo(self, call_data: str) -> None:
        """
        finds count of photo in call_data string and assign it to self.need_photo.

        :param call_data: callback data from ScenarioKeyboards.is_photo keyboard.
        :type call_data: str
        :return: None
        """

        try:
            self.need_photo = int(search(r"\d+", call_data).group())
        except AttributeError:
            self.need_photo = False

    def children_dict_formatting(self) -> None:
        """
        Method to format children dict to 'dict[str, str]'

        :return: None
        """

        for key, value in self.children.items():
            if value:
                new_val = [str(i) for i in value]
                self.children[key] = ", ".join(new_val)
            else:
                self.children[key] = ""

    def prepare_request_data(self) -> Tuple[Dict[str, Union[date, str]], Dict[str, str], Optional[Dict[str, str]]]:
        """
        Prepares a querystring for query to find hotels (rapidapi)

        :return: formatted data for query to find hotels.
        :rtype: Tuple[Dict[str, Union[date, str]], Dict[str, str], Optional[Dict[str, str]]]
        """

        self._adults = {f"adults{i + 1}": self.adults[i] for i in range(len(self.adults))}
        request_data = {
            "destination_id": self.destination_id,
            "hotel_count": self.hotel_count,
            "check_in": self.check_in,
            "check_out": self.check_out,
            "min_price": self.min_price,
            "max_price": self.max_price
        }
        if self.children:
            self.children_dict_formatting()
        return request_data, self._adults, self.children

    @classmethod
    def reboot(cls, user_id: int) -> 'UserRequest':
        """
        Reset UserRequest instance to default state.

        :param user_id: id of UserRequest instance needed to be restored.
        :type user_id: int
        :return: UserRequest instance with passed id
        :type: UserRequest
        """

        remove_user_state_from_db(user_id=user_id)
        return UserRequest(user_id)


class ScenarioKeyboards(ABC):
    """
    Abstract class to prepare keyboards according to scenario.
    """

    @classmethod
    def clear_marks(cls, markup_keyboard: InlineKeyboardMarkup) -> InlineKeyboardMarkup:
        """
        Gets an InlineKeyboardMarkup instance with marked button (user's choice).
        Returns an InlineKeyboardMarkup instance without marks.

        :param markup_keyboard: an InlineKeyboardMarkup instance with marked button.
        :type markup_keyboard: InlineKeyboardMarkup.
        :return:an InlineKeyboardMarkup instance without marks.
        :rtype InlineKeyboardMarkup
        """

        for keyboard in markup_keyboard.keyboard:
            for kb_obj in keyboard:
                if kb_obj.text.startswith(current_choice['em'] + " "):
                    kb_obj.text = kb_obj.text[2:]
        return markup_keyboard

    @classmethod
    def mark_user_choice(cls, markup_keyboard: InlineKeyboardMarkup, choice: str) -> InlineKeyboardMarkup:
        """
        Gets an InlineKeyboardMarkup instance without marks
        and text to find in buttons text.
        Finds a button with same text and marks this button.
        Returns an InlineKeyboardMarkup instance with mark.

        :param markup_keyboard: an InlineKeyboardMarkup instance with marked button.
        :type markup_keyboard: InlineKeyboardMarkup.
        :param: choice: user choice which needed to be marked.
        :type choice: str
        :return:an InlineKeyboardMarkup instance without marks.
        :rtype InlineKeyboardMarkup
        """

        markup_keyboard = cls.clear_marks(markup_keyboard)
        for keyboard in markup_keyboard.keyboard:
            for kb_obj in keyboard:
                if kb_obj.text == choice:
                    kb_obj.text = current_choice['em'] + " " + kb_obj.text
                    return markup_keyboard

    @classmethod
    def generate_edit_kb(cls, string: str) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with callback data = passed `string`

        :param string: callback for button
        :type: str
        :return: an InlineKeyboardMarkup instance with button callback = passed string
        :rtype: InlineKeyboardMarkup
        """
        edit_kb = InlineKeyboardMarkup(row_width=1)
        edit_kb.add(InlineKeyboardButton(text=kb_text["main_edit_kb"],
                                         callback_data=f"{string}"))
        return edit_kb

    @classmethod
    def generate_set_location_kb(cls, locations: Dict[str, str]) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with list of locations to choose.
        buttons text is got from `location` keys, buttons callback is got from
        `locations` values.

        :param locations: dict with pairs 'location name': 'location id'.
        :type locations: Dict[str, str]
        :return: InlineKeyboardMarkup instance with list of locations to choose.
        :rtype: InlineKeyboardMarkup
        """

        keyboard = InlineKeyboardMarkup(row_width=1)
        buttons = [InlineKeyboardButton(text=location,
                                        callback_data=f"id={location_id}")
                   for location, location_id in locations.items()]
        return keyboard.add(*buttons)

    @classmethod
    def generate_edit_rooms_kb(cls, user_adults: int) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with
        main menu for managing rooms in current query.

        :param user_adults: current number of rooms in query. InlineKeyboardMarkup instance
            will miss 'add room' button if user_adults > 7.
        :type user_adults: int
        :return: an InlineKeyboardMarkup instance with buttons to add room,
            edit rooms of start the search.
        :rtype: InlineKeyboardMarkup
        """

        edit_rooms_kb = InlineKeyboardMarkup(row_width=1)
        edit_rooms_kb.add(InlineKeyboardButton(text=kb_text["main_edit_kb_rooms"]["edit"],
                                               callback_data=f"change_room"))
        if user_adults <= 7:
            edit_rooms_kb.add(InlineKeyboardButton(text=kb_text["main_edit_kb_rooms"]["add_room"],
                                                   callback_data=f"change_new_room"))
        edit_rooms_kb.add(InlineKeyboardButton(text=kb_text["main_edit_kb_rooms"]["start_search"],
                                               callback_data="finish"))
        return edit_rooms_kb

    @classmethod
    def num_of_hotels(cls) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with 10 buttons
        to choice number of hotels in current query.

        :return: a keyboard to choose number of hotels.
        :rtype: InlineKeyboardMarkup
        """

        hotels = InlineKeyboardMarkup(row_width=5)
        buttons = [InlineKeyboardButton(text=f"{i + 1}",
                                        callback_data=f"h={i + 1}") for i in range(10)]
        return hotels.add(*buttons)

    @classmethod
    def is_photo(cls, need: bool = False) -> InlineKeyboardMarkup:
        """
        Method to create keyboards for ask about photos.
        need = False:
            returns a keyboard to set photo's presence in response.
        need = True:
            returns a keyboard to set number of photos in response (from 1 to 10).

        :param need: define presence of buttons to set number of photos.
        :type need: bool
        :return: a keyboard for asking about photos.
        :rtype: InlineKeyboardMarkup
        """

        buttons = []
        photo_kb = InlineKeyboardMarkup(row_width=5)
        if not need:
            buttons.append(InlineKeyboardButton(text=kb_text["photo"]["positive"],
                                                callback_data=f"photo+"))
            buttons.append(InlineKeyboardButton(text=kb_text["photo"]["negative"],
                                                callback_data="photo-"))
        else:
            buttons.extend([InlineKeyboardButton(text=f"{i}",
                                                 callback_data=f"photo{i}")
                            for i in range(1, 11)])
        return photo_kb.add(*buttons)

    @classmethod
    def ask_about_children_kb(cls, room: int) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with buttons to change
        presence of children in current room (+ or -).

        :param room: current room (starts from 0)
        :type room: int
        :return: an InlineKeyboardMarkup instance with buttons to change
            presence of children in current room (+ or -)
        :rtype: InlineKeyboardMarkup
        """

        keyboard = InlineKeyboardMarkup(row_width=2)
        keyboard.add(InlineKeyboardButton(text="+",
                                          callback_data=f"+,{room}"),
                     InlineKeyboardButton(text="-",
                                          callback_data=f"-,{room}"))
        return keyboard

    @classmethod
    def generate_adults_keyboard(cls, cur_room: int) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance for setting number of adults
        in current room.

        :param cur_room: room to set number of adults. Starts from 0.
        :type cur_room: int
        :return: an InlineKeyboardMarkup instance for setting number of adults
            in current room.
        :rtype: InlineKeyboardMarkup
        """

        adults_in_room_keyboard = InlineKeyboardMarkup(row_width=4)
        buttons = [InlineKeyboardButton(text=f"{i + 1}",
                                        callback_data=f"my_a{i + 1},{cur_room}")
                   for i in range(14)]
        return adults_in_room_keyboard.add(*buttons)

    @classmethod
    def generate_keyboard_for_children_step(cls, usr: UserRequest, room: int) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance with buttons to set
        age of child in current room (from 0 to 17).

        :param usr: UserRequest instance relates to user making a query
        :type: usr: UserRequest
        :param room: a room to add child.
        :type room: int
        :return: an InlineKeyboardMarkup with buttons to set
            age of child in current room or leave this step.
        :rtype: InlineKeyboardMarkup
        """

        keyboard = InlineKeyboardMarkup(row_width=6)
        button = InlineKeyboardButton(text="<1",
                                      callback_data=f"ch_age={0},{room}")
        buttons = [InlineKeyboardButton(text=f"{i}",
                                        callback_data=f"ch_age={i},{room}") for i in range(1, 18)]
        keyboard.add(button, *buttons)
        available_rooms = []
        for item in usr.memory["rooms"].keys():
            available_rooms.append(item)
        if room + 1 in available_rooms:
            keyboard.row(InlineKeyboardButton(text=kb_text["children"]["complete"],
                                              callback_data=f"-,{room}"))
        elif len(usr.children[f"children{room + 1}"]) > 0:
            keyboard.row(InlineKeyboardButton(text=kb_text["children"]["next_step"],
                                              callback_data=f"-,{room}"))
        else:
            keyboard.row(InlineKeyboardButton(text=kb_text["children"]["without"],
                                              callback_data=f"-,{room}"))
        return keyboard

    @classmethod
    def generate_edit_prev_data_kb(cls, user: UserRequest) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance to edit
        info user's in main message.

        :param user: UserRequest instance relates to user making a query
        :type user: UserRequest
        :return: an InlineKeyboardMarkup with buttons to edit the entered information.
        :rtype: InlineKeyboardMarkup
        """

        edit_prev_data_kb = InlineKeyboardMarkup(row_width=1)
        buttons = []
        button = InlineKeyboardButton(text=kb_text["main_edit_kb_details"]["location"],
                                      callback_data="location")
        if user.memory["hotel_count"]:
            buttons.append(InlineKeyboardButton(text=kb_text["main_edit_kb_details"]["hotel_count"],
                                                callback_data="hotel_count"))
        if user.memory["dates"]["check_in"]:
            buttons.append(InlineKeyboardButton(text=kb_text["main_edit_kb_details"]["check_in"],
                                                callback_data="check_in"))
        if user.memory["dates"]["check_out"]:
            buttons.append(InlineKeyboardButton(text=kb_text["main_edit_kb_details"]["check_out"],
                                                callback_data="check_out"))
        buttons.append(InlineKeyboardButton(text=kb_text["back"],
                                            callback_data="change_back"))
        return edit_prev_data_kb.add(button, *buttons)

    @classmethod
    def generate_edit_rooms_prev_data_kb(cls, user: UserRequest) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance to edit
        info in user's main rooms message.

        :param user: UserRequest instance relates to user making a query
        :type user: UserRequest
        :return: an InlineKeyboardMarkup with buttons to edit the entered information.
        :rtype: InlineKeyboardMarkup
        """

        edit_rooms_prev_data_kb = InlineKeyboardMarkup(row_width=1)
        buttons = []
        button = InlineKeyboardButton(text=kb_text["edit_rooms_prev_data"]["edit_1_room"],
                                      callback_data=f"change_0_room")
        if user.total_room > 1:
            for room in range(2, user.total_room + 1):
                buttons.append(InlineKeyboardButton(text=kb_text["edit_rooms_prev_data"]["edit_room"].format(room),
                                                    callback_data="change_{}_room".format(room-1)))
            buttons.append(InlineKeyboardButton(text=kb_text["edit_rooms_prev_data"]["delete_room"],
                                                callback_data="change_delete"))
        buttons.append(InlineKeyboardButton(text=kb_text["back"],
                                            callback_data="change_back"))
        return edit_rooms_prev_data_kb.add(button, *buttons)

    @classmethod
    def generate_delete_rooms_kb(cls, total_rooms: int) -> InlineKeyboardMarkup:
        """
        Creates an InlineKeyboardMarkup instance to delete rooms.

        :param total_rooms: number of rooms in query.
        :type total_rooms: int
        :return: InlineKeyboardMarkup instance to delete rooms.
        :rtype: InlineKeyboardMarkup
        """

        delete_rooms_kb = InlineKeyboardMarkup(row_width=2)
        buttons = [InlineKeyboardButton(text=kb_text["delete_rooms"].format(i + 1),
                                        callback_data=f"change_d{i}_room") for i in range(total_rooms)]
        buttons.append(InlineKeyboardButton(text=kb_text["back"],
                                            callback_data="change_back"))
        return delete_rooms_kb.add(*buttons)


DEF_KEYBOARDS = {
    "main_changes": ScenarioKeyboards.generate_edit_kb("main"),
    "num_of_hotels": ScenarioKeyboards.num_of_hotels(),
    "need_photo": ScenarioKeyboards.is_photo(need=False),
    "need_photo_true": ScenarioKeyboards.is_photo(need=True)
}
