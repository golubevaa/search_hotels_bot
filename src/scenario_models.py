"""
methods that implement the bot script (creation message texts, keyboards, etc)
"""

from telegram_bot_calendar import DetailedTelegramCalendar
from telebot.types import InputMediaPhoto
from src.base import ScenarioKeyboards, DEF_KEYBOARDS
from src.hotels_api import get_hotel_photos, get_hotels_dict
from src.bot_text import main_message_text_dict, hotels_link, history_dict
from src.auxiliary_functions import *
from db.history_db import push_to_db, get_from_db
from datetime import datetime


def generate_main_message_text(user_memory: Dict[str, Any], without_rooms=True) -> str:
    """
    Creates the string to messages according to passed dict (finds "text" keys).
    Ignores value in 'rooms' key if without_rooms is true.
    Ignores all value except 'rooms' key's value if without_rooms is false.

    :param user_memory: dict with data relates to current query (from user memory dict)
    :type user_memory: Dict[any]
    :param without_rooms: This flag identifies type of text to be prepared.
        If true: text for main message will be prepared.
        If false: text for main rooms message will be prepared.
    :return: text for main messages.
    :rtype: str
    """

    text = ""

    if not without_rooms:
        user_memory = dict(sorted(user_memory.items()))

    for step, value in user_memory.items():
        if step == "rooms" and without_rooms:
            break
        else:
            if isinstance(step, int):
                text += main_message_text_dict["room_header"].format(step + 1)
        if value:
            try:
                text += "{}\n".format(value['text'])
            except KeyError:
                text += generate_main_message_text(value)

    return text


def msg_text_depends_on_msg_id(user: UserRequest, additional_text: str, msg_id: int) -> str:
    """
    Compares passed message_id with user's main message and
    creates text for messages according to comparison results.

    :param user: UserRequest instance which will get new text.
    :type user: UserRequest
    :param additional_text: text which will be added to main text (asking for choose something).
    :type additional_text: str
    :param msg_id: id of message which will be edited.
    :type msg_id: int
    :return: text for message.
    :rtype: str
    """

    text = ""
    if user.main_message == msg_id:
        text += generate_main_message_text(user.memory) + "\n\n"
    return text + additional_text


def build_calendar(user: Optional[UserRequest] = None, _id: int = 1) -> DetailedTelegramCalendar:
    """
    Creates Calendar keyboards in initial stage to set check_in and check_out.

    :param user: Owner of calendar (calendar will be sent to the user).
    :type user: UserRequest
    :param _id: Calendar id. 1 if check_in, 2 if check_out.
    :type _id: int
    :return: a calendar keyboard in initial stage.
    :rtype: DetailedTelegramCalendar
    """

    kwargs = create_calendar_kwargs(_id=_id, user=user)
    return DetailedTelegramCalendar(**kwargs).build()


def build_calendar_callback(call_data: str,
                            user: Optional[UserRequest] = None, _id: int = 1) -> DetailedTelegramCalendar:
    """
    Modifies Calendar keyboards set check_in and check_out
    (shows selected years and months).

    :param call_data: special value from CallbackQuery (call.data) to
        identify required modifications.
    :type call_data: str
    :param user: Owner of calendar (calendar will be sent to the user).
    :type user: UserRequest
    :param _id: Calendar id. 1 if check_in, 2 if check_out.
    :type _id: int
    :return: a calendar keyboard in modified stage
        (will change initial calendar according to user's choice).
    :rtype: DetailedTelegramCalendar
    """

    kwargs = create_calendar_kwargs(_id=_id, user=user)
    return DetailedTelegramCalendar(**kwargs).process(call_data)


def get_main_message_text_and_markup(call_data: str, msg_id: int,
                                     user: UserRequest) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Creates modified main message text and their keyboard according to user's choice.

    :param call_data: call data from received CallbackQuery
        related to changes in main message.
    :param msg_id: id of message with main info.
    :type msg_id: int
    :type: call_data: str
    :param user: user which changes main message.
    :type user: UserRequest
    :return: text and new keyboard for main message
    :rtype: Tuple[str, InlineKeyboardMarkup]
    """

    markup = None
    text = ""
    if call_data == "main":
        text = generate_main_message_text(user_memory=user.memory)
        markup = ScenarioKeyboards.generate_edit_prev_data_kb(user)
        return text, markup

    base_text = bot_answers[call_data]["set_" + call_data]
    if call_data in ("location", "hotel_count"):
        markup = user.memory[call_data]["markup"]
        text = msg_text_depends_on_msg_id(user=user,
                                          additional_text=base_text,
                                          msg_id=msg_id)

    elif call_data == "check_in":
        markup = build_calendar(user=user,
                                _id=1)
        text = msg_text_depends_on_msg_id(user=user,
                                          additional_text=base_text,
                                          msg_id=msg_id)
    elif call_data == "check_out":
        markup = build_calendar(user=user,
                                _id=2)
        text = msg_text_depends_on_msg_id(user=user,
                                          additional_text=base_text,
                                          msg_id=msg_id)

    return text, markup


def add_children_info_to_user_memory(user: UserRequest, room: int,
                                     disable_guest_cycle: bool) -> Tuple[str, Optional[int]]:
    """
    Collects data about children in current user's room.
    Saves it in user's memory dict.
    Prepares new text to main rooms message.
    Return the text and current number of children in room.

    :param user: UserRequest instance which creates a room with children.
    :type user: UserRequest
    :param room: room number (starts from 0). Method will count children in this room.
    :param disable_guest_cycle: True if it's necessary to disable editing of this room.
    :type disable_guest_cycle: bool
    :type room: int
    :return: ext and current number of children in room.
    :rtype: Tuple[str, Optional[int]]
    """

    try:
        children_in_room = len(user.children[f"children{room + 1}"])
    except KeyError:
        children_in_room = None

    if children_in_room:
        user.memory["rooms"][room].update({
            "children": {
                "text": main_message_text_dict["children"].format(children_in_room)
            }
        })

    if disable_guest_cycle:
        user.guest_cycle[room] = False
    update_user_state(user=user)
    text = generate_main_message_text(user_memory=user.memory["rooms"])
    return text, children_in_room


def prepare_text_and_kb_to_adults_stage(user: UserRequest, room: int, edit: bool) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Starts guest cycle in this room. It means inability to start another room editing
    before this room will be fully created (it will be completed
    after setting adults and children in room (if children are presented)).

    Creates a keyboard and text to set room's adults.
    Increases the number of rooms by 1 if the room just created (edit = false).

    :param user: UserRequest instance which creates or edit a room.
    :type user: UserRequest
    :param room: room number (starts from 0).
    :type room: int
    :param edit: True if room already exists. In this case user.total_room won't be increased.
        False if room just created. In this case user.total_room will be increased by 1.
    :type edit: bool
    :return: a keyboard and text to set room's adults.
    :rtype: Tuple[str, InlineKeyboardMarkup]
    """

    user.guest_cycle[room] = True
    if not edit:
        user.total_room += 1
        keyboard = ScenarioKeyboards.generate_adults_keyboard(cur_room=room)
    else:
        keyboard = check_button_callbacks_correctness(user.memory["rooms"][room]["adults"]["markup"], room)
    text = main_message_text_dict["rooms_text"]["adults"].format(room + 1)
    update_user_state(user=user)
    return text, keyboard


def prepare_text_and_kb_to_children_stage(user: UserRequest, room: int) -> Tuple[str, InlineKeyboardMarkup]:
    """
    Creates a key-value pair in user's children dict for current
    room if it doesn't exist.
    Returns a text and a keyboard to set age of current children in passed room.

    :param user: UserRequest instance which set children a room.
    :type user: UserRequest
    :param room: room number (starts from 0).
    :type room: int
    :return: a text and a keyboard to set age of current children in passed room.
    :rtype: Tuple[str, InlineKeyboardMarkup]
    """

    if f"children{room + 1}" not in user.children.keys():
        user.children[f"children{room + 1}"] = []
    cur_child = len(user.children[f"children{room + 1}"]) + 1

    keyboard = ScenarioKeyboards.generate_keyboard_for_children_step(usr=user,
                                                                     room=room)
    text = main_message_text_dict["rooms_text"]["children"].format(cur_child, room + 1)
    update_user_state(user=user)
    return text, keyboard


def save_current_stage_main_message_info(
        call_markup: Optional[InlineKeyboardMarkup],
        user: UserRequest, stage: str, format_arg: Any,
        call_text: Optional[str] = "") -> Tuple[str, Optional[InlineKeyboardMarkup]]:
    """
    Handles all callback queries related to modifications in main message.
    Marks previous user's choice at keyboard and saves it to user's memory dict.
    Returns text and keyboard to modified message.

    :param call_markup: keyboard which needed to be marked and saved.
    :type call_markup: InlineKeyboardMarkup
    :param user: UserRequest instance which makes a query.
    :type user: UserRequest
    :param stage: stage which was modified: 'location', 'hotel_count', 'check_in', 'check_out'
    :type stage: str
    :param format_arg: arguments to format message string related to current stage.
    :param call_text: callback data str to save callback from calendars
    :type call_text: Optional[str]
    :return: text and keyboard to modified message.
    :rtype: Tuple[str, Optional[InlineKeyboardMarkup]]
    """

    if call_markup:
        call_markup = ScenarioKeyboards.mark_user_choice(markup_keyboard=call_markup,
                                                         choice=format_arg)
    if stage in user.memory.keys():
        user.memory[stage]["text"] = main_message_text_dict[stage].format(format_arg)
        user.memory[stage]["markup"] = call_markup
    else:
        user.memory["dates"][stage]["text"] = \
            main_message_text_dict["dates"][stage].format(format_arg)
        user.memory["dates"][stage].update({"last_callback": call_text})

    edit_markup = DEF_KEYBOARDS["main_changes"]
    text = generate_main_message_text(user_memory=user.memory)
    update_user_state(user=user)
    return text, edit_markup


def add_adults_info_to_user_memory(
        call_markup: InlineKeyboardMarkup, user: UserRequest, room: int, format_arg: str) -> str:
    """
    Handles callback queries to set or modify adults in rooms.
    Marks previous user's choice at keyboard and saves it to user's memory dict.
    Saves adults of current room in UserRequest instance.
    Creates new text of main rooms message.

    :param call_markup: keyboard which needed to be marked and saved.
    :type call_markup: InlineKeyboardMarkup
    :param user: UserRequest instance which makes a query.
    :type user: UserRequest
    :param room: room number (starts from 0).
    :type room: int
    :param format_arg: arguments to format message string related to adults stage.
    :return: text to modified main rooms message.
    :rtype: str
    """
    call_markup = ScenarioKeyboards.mark_user_choice(markup_keyboard=call_markup,
                                                     choice=format_arg)
    user.memory["rooms"].update({
        room: {
            "adults": {
                "markup": call_markup,
                "text": main_message_text_dict["adults"].format(format_arg)
            }
        }
    })

    try:
        user.adults[room] = int(format_arg)
    except IndexError:
        user.adults.append(int(format_arg))

    update_user_state(user=user)
    text = generate_main_message_text(user_memory=user.memory["rooms"])
    return text


def define_location_name(user: UserRequest, call: CallbackQuery) -> None:
    """
    Finds location name using info from CallbackQuery
    and assigns it to UserRequest instance location_name.
    Clears UserRequest instance start_search and start_search_pool attributes.
    Removes all messages which were contained in start search pool.

    :param user: UserRequest instance
    :type user: UserRequest
    :param call: CallbackQuery with keyboard related to location choose.
    :type call: CallbackQuery
    :return: None
    """

    if not user.main_message:
        user.main_message = call.message.message_id
    user.location_name = find_location_name(call_json=call.json,
                                            location_id=call.data)
    user.start_search = False
    for msg in user.start_search_pool:
        bot.delete_message(chat_id=user.user_id,
                           message_id=msg)
    update_user_state(user=user)
    user.start_search_pool = []


def prepare_hotels_message_items(_id: int, data: Dict[str, str],
                                 need_photo: Union[bool, int]) -> Tuple[str, Union[List[InputMediaPhoto], bool]]:
    """
    Creates a text for message with hotel info.
    Creates a list wth InputMediaPhoto if the need_photo not False.

    :param _id: hotel id. Will be used to create a link.
    :type _id: int
    :param data: a dict with all hotel info.
    :type data: Dict[str, str]
    :param need_photo: user.need_photo argument.
        a list with photo will be prepared if the need_photo is int.
    :type need_photo: Union[bool, int]
    :return: a text for message with hotel info and a list
        with InputMediaPhoto (in cases where need_photo not False).
    :rtype: Tuple[str, Union[List[InputMediaPhoto], bool]]
    """

    text = ""
    bot_photos = None
    for key, value in data.items():
        text += f"{key}: {value}\n"
    url = "{0}{1}/".format(hotels_link["link"], _id)
    text += "\n[{0}]({1})".format(hotels_link["text"], url)
    if need_photo:
        photos = get_hotel_photos(hotel_id=_id,
                                  num_of_photo=need_photo)
        if photos:
            bot_photos = [InputMediaPhoto(media=photos[i]) if i != 0
                          else InputMediaPhoto(media=photos[i],
                                               caption=text,
                                               parse_mode='MARKDOWN') for i in range(len(photos))]
    return text, bot_photos


def send_hotels_messages(hotels: Dict[int, Dict[str, str]], user: UserRequest) -> List[str]:
    """
    Sends messages with hotels info.

    :param hotels: dict with hotels info.
    :type hotels: Dict[int, Dict[str, str]]
    :param user: user which will receive the messages.
    :type user: UserRequest
    :return: List of strings with hotels info (will be used to save search info to DB).
    :rtype: List[str]
    """
    message_counter = 0
    list_for_history_db = []
    for _id, data in hotels.items():
        list_for_history_db.append(f"{_id}***{hotels[_id]['Отель']}")
        text, bot_photos = prepare_hotels_message_items(_id=_id,
                                                        data=data,
                                                        need_photo=user.need_photo)
        if bot_photos:
            try:
                bot.send_media_group(chat_id=user.user_id,
                                     media=bot_photos)
                message_counter += 1
                continue
            except ApiTelegramException:
                continue
        elif not bot_photos and user.need_photo:
            text = bot_answers["search_and_res"]["show_hotels_info"]["photo_issue"] + text
        bot.send_message(text=text,
                         chat_id=user.user_id,
                         parse_mode='MARKDOWN',
                         disable_web_page_preview=True)
        message_counter += 1
    if message_counter < int(user.hotel_count):
        text = bot_answers["search_and_res"]["show_hotels_info"]["less_than_required"].format(message_counter)
        bot.send_message(text=text,
                         chat_id=user.user_id,
                         disable_web_page_preview=True)
    return list_for_history_db


def delete_room(user: UserRequest, room: int) -> None:
    """
    Deletes the room from current user's query

    :param user: user which needs to delete the room
    :type user: UserRequest
    :param room: room to delete (starts from 0)
    :type room: int
    :return: None
    """

    list_of_rooms = sorted(user.memory["rooms"].keys())

    if room != list_of_rooms[-1]:
        for key in list_of_rooms:
            if key == room:
                del user.memory["rooms"][room]
                del user.children[f"children{room + 1}"]
            elif key > room:
                user.memory["rooms"][key - 1] = user.memory["rooms"][key]
                user.children[f"children{key}"] = user.children[f"children{key + 1}"]

    del user.memory["rooms"][list_of_rooms[-1]]
    del user.children[f"children{list_of_rooms[-1] + 1}"]
    user.adults.pop(room)
    user.total_room -= 1
    update_user_state(user=user)


def show_hotels_info(user: UserRequest) -> None:
    """
    Creates and sends the messages with hotels according to user's info.

    :param user: user which will receive the messages.
    :type user: UserRequest
    :return: None
    """

    querystring, adults, children = user.prepare_request_data()
    hotels, min_distance = get_hotels_dict(**querystring,
                                           adults=adults,
                                           children=children,
                                           command=user.command,
                                           distance=user.distance)
    if hotels:
        list_for_db = send_hotels_messages(hotels=hotels, user=user)
        if list_for_db:
            push_to_db(telegram_id=user.user_id,
                       command=user.command,
                       date=datetime.now(),
                       hotel=list_for_db,
                       location=user.location_name)

    else:
        text = bot_answers["search_and_res"]["show_hotels_info"]["not_found"]
        if user.command == "/bestdeal" and min_distance:
            text += bot_answers["search_and_res"]["show_hotels_info"]["nearest_hotel"].format(min_distance)
        bot.send_message(text=text,
                         chat_id=user.user_id)


def send_history(user: UserRequest) -> None:
    """
    Searches info about previous searches in DB and sends it to user.

    :param user: the user to send history
    :type user: UserRequest
    :return: None
    """

    history_from_db = get_from_db(user.user_id)
    if history_from_db:
        for message_text in history_from_db:
            bot.send_message(text=message_text,
                             chat_id=user.user_id,
                             parse_mode="MARKDOWN",
                             disable_web_page_preview=True)
    else:
        bot.send_message(text=history_dict["empty"],
                         chat_id=user.user_id)


