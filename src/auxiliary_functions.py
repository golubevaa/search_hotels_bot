"""
auxiliary functions for hotels bot (decorators, check warnings, etc)
"""

from src.bot_text import current_choice, commands,\
    common_commands, bot_answers, warnings_dict, answer_callback_warnings
from src.bot_stages import stages
from telebot.types import Message, CallbackQuery, InlineKeyboardMarkup
from telebot.apihelper import ApiTelegramException
from src.base import UserRequest
from db.userstates_db import *
from typing import Dict, Any, Optional, Callable, Union, Tuple, List
from functools import wraps
from bot_settings import bot
from re import match
from datetime import date, timedelta


def set_stage(func: Callable) -> Callable:

    """ Decorator to set stage to UserRequest instances stage parameter. """

    @wraps(func)
    def wrapped_func(*args, **kwargs) -> Any:
        if not kwargs:
            try:
                user = list(filter(lambda arg: isinstance(arg, UserRequest), args))[0]
            except IndexError:
                user = UserRequest.get_user(list(filter(lambda arg: isinstance(arg, Message), args))[0].from_user.id)
        else:
            try:
                user = kwargs["user"]
            except KeyError:
                user = UserRequest.get_user(kwargs["msg"].from_user.id)
        if stages[user.stage] < stages[func.__name__]:
            user.stage = func.__name__
            update_user_state(user=user)
        result = func(*args, **kwargs)
        return result

    return wrapped_func


def remove_keyboard(chat_id: int, msg_id: int) -> bool:
    """
    Removes keyboard from message. Returns True if keyboard was exist.

    :param chat_id: id of chat.
    :type chat_id: int
    :param msg_id: id of message with keyboard.
    :type msg_id: int
    :return: True if keyboard was exist else False.
    :rtype: bool
    """

    try:
        bot.edit_message_reply_markup(chat_id=chat_id,
                                      message_id=msg_id,
                                      reply_markup=None)
        return True
    except ApiTelegramException:
        return False


def create_calendar_kwargs(_id: int, user: UserRequest) -> Dict[str, Union[str, date]]:
    """
    Creates a dict with parameters to build calendar keyboard.

    :param _id: Calendar id. 1 if check_in, 2 if check_out
    :type _id: int
    :param user: Owner of calendar (calendar will be sent to the user).
    :type user: UserRequest
    :return: dict with parameters to build calendar keyboard
    :rtype: Dict[str, Union[str, date]]
    """
    equals = {1: "check_in", 2: "check_out"}
    kwargs = {"calendar_id": _id, "locale": "ru"}

    if _id == 1:
        kwargs.update({
            "current_date": date.today(),
            "min_date": date.today(),
            "max_date": date.today() + timedelta(days=365)
        })
    else:
        kwargs.update({
            "current_date": date.today(),
            "min_date": user.check_in + timedelta(days=1),
            "max_date": user.check_in + timedelta(days=366),
        })
    if getattr(user, equals[_id]):
        button = {"text": f"{current_choice['em']} {current_choice['text']}: {getattr(user, equals[_id])}",
                  "callback_data": user.memory["dates"][equals[_id]]["last_callback"]}
        kwargs.update({'additional_buttons': [button]})

    return kwargs


def define_next_stage(next_func: Callable, attr: Any) -> Callable:
    """
    Decorator to set attributes values

    :param next_func:
    :param attr:
    :return:
    """

    def next_stage_decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapped_func(call) -> None:
            result = func(call)
            instance = UserRequest.get_user(user_id=call.message.chat.id)
            if result:
                setattr(instance, attr, result)
                update_user_state(instance)
                if stages[next_func.__name__] > stages[instance.stage]:
                    next_func(instance)

        return wrapped_func

    return next_stage_decorator


def delete_message_if_not_main(call_message_id: int, main_message: int, additional_bool: bool, **kwargs: Any) -> None:
    """
    Deletes message if message id != main message.
    Could accept additional condition as additional bool argument.

    :param call_message_id: id of message which may be deleted.
    :type call_message_id: int
    :param main_message: id of main message
    :type main_message: int
    :param additional_bool: additional condition
    :type additional_bool: bool
    :return: None
    """

    if call_message_id != main_message and additional_bool:
        bot.delete_message(**kwargs)


def check_destination_cycle(func: Callable) -> Callable:
    """
    Decorator to block all messages except known commands.
    """

    @wraps(func)
    def wrapped_func(message: Message):
        _id = message.from_user.id
        if message.text in (*commands, *common_commands.keys()):
            return func(message)
        if get_user_state_from_db(_id):
            user = UserRequest.get_user(_id)
            if not user.start_search:
                return func(message)
            msg = bot.reply_to(text=bot_answers["location"]["check_start_cycle"],
                               message=user.start_search)
            user.start_search_pool.append(msg.message_id)
            update_user_state(user=user)
        return func(message)

    return wrapped_func


def check_rooms_warnings(*args, guest_cycle: Dict[int, bool], call_data: str) -> Optional[str]:
    """
    Check guest_cycle values (value is True if room in edit stage).
    Creates a warning text if any of values is True.

    :param guest_cycle: guest_cycle dict from UserRequest instance.
    :type guest_cycle: Dict[int, bool]
    :param call_data: data received from CallbackQuery
        related to modify any of  user's rooms.
    :type call_data: str
    :param args: values to format warning string (rooms numbers)
    :return: warning string if any of user's rooms in edit stage else None.
    :rtype: Optional[str]
    """

    warning = None
    if any(guest_cycle.values()):
        room = [key for key, value in guest_cycle.items() if value]
        for key, value in warnings_dict.items():
            if match(key, call_data):
                warning = value.format(room[0] + 1, *args)
    return warning


def find_location_name(call_json: Dict[str, Any], location_id: str) -> str:
    """
    Find keyboard buttons text in callback.json using callback data.

    :param call_json: callback.json from CallBack Query.
    :type call_json: dict
    :param location_id: callback data which needed to find.
    :type location_id: str
    :return: text of button which appropriated with passed callback.
    :rtype: str
    """

    for button in call_json["message"]["reply_markup"]["inline_keyboard"]:
        for data in button:
            if data["callback_data"] == location_id:
                return data["text"]


def check_dates(check_in, check_out) -> Optional[str]:
    """
    Check dates correctness (Check-in date < check-out date).

    :param check_in: check-in date
    :type check_in: date
    :param check_out: check-out date
    :type check_out: date
    :return: string with warning if issue was observed. None if there is no issue.
    :rtype Optional[str]
    """

    if check_in > check_out:
        return answer_callback_warnings["dates"]["less"]
    elif check_in == check_out:
        return answer_callback_warnings["dates"]["equal"]

    return ""


def check_men_count(user: UserRequest) -> Optional[str]:
    """
    Check that total number of men <= 20.

    :param user: UserRequest instance which needed to be checked.
    :type user: UserRequest
    :return: string with warning if issue was observed. None if there is no issue.
    :rtype Optional[str]
    """

    children = user.count_child()
    adults = sum(user.adults)
    if children + adults > 20:
        return answer_callback_warnings["men"]

    return ""


def check_quest_cycle(user: UserRequest) -> Optional[str]:
    """
    Check that there are no rooms in edit state.

    :param user: UserRequest instance which needed to be checked.
    :type user: UserRequest
    :return: string with warning if issue was observed. None if there is no issue.
    :rtype Optional[str]
    """

    if any(user.guest_cycle.values()):
        room = [k for k, v in user.guest_cycle.items() if v is True]
        return answer_callback_warnings["rooms"].format(room[0] + 1)

    return ""


def check_booking_for_correctness(user: UserRequest) -> Optional[str]:
    """
    Check the correctness of user's query data.
    Requirements:
        Check-in date is less than check-out date.
        Number of men under 21.
        There's no rooms in progress.
    creates the warning text in negative cases.

    :param user: UserRequest instance which needed to be checked.
    :type user: UserRequest
    :return: string with warning if issue was observed. None if there is no issue.
    :rtype Optional[str]
    """

    result = ""
    result += check_dates(check_in=user.check_in,
                          check_out=user.check_out)
    result += check_men_count(user=user)
    result += check_quest_cycle(user=user)

    return result


def prepare_instance_to_new_search(user: UserRequest, new_command: str) -> UserRequest:
    """
    Clears user's 'start search pool'. Remove all reply markups related to previous query.
    Remove user from user_state DB. Assign new command to instance and updates DB.

    :param user: UserRequest instance needed to be restored.
    :type user: UserRequest
    :param new_command: command for new search
    :type new_command: str
    :return: UserRequest ready to new search
    :rtype: UserRequest
    """

    msgs = [i for i in (user.main_message, user.main_rooms_message) if i is not None]
    msgs.extend([i.message_id for i in (user.start_search, user.cur_step) if isinstance(i, Message)])
    for msg in msgs:
        if not remove_keyboard(chat_id=user.user_id, msg_id=msg):
            remove_keyboard(chat_id=user.user_id, msg_id=msg - 1)

    for msg in user.start_search_pool:
        bot.delete_message(chat_id=user.user_id,
                           message_id=msg)
    user.start_search_pool = []
    user = UserRequest.reboot(user_id=user.user_id)
    user.command = new_command
    user.stage = "set_location"
    update_user_state(user)
    return user


def send_answer_callback_query_rooms_stage(call: CallbackQuery, *args) -> bool:
    """
    Check guest cycle before editing a room. Send answer_callback_query if any
    of rooms in editing stage.

    :param call: a CallbackQuery with modify action.
    :type call: CallbackQuery
    :param args: args to pass check_rooms_warnings.
    :return: True if worning is observed. None if there is no warnings.
    :rtype: bool
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)
    warning = check_rooms_warnings(*args,
                                   guest_cycle=user.guest_cycle,
                                   call_data=call.data)
    if warning:
        bot.answer_callback_query(callback_query_id=call.id,
                                  text=warning)
        return True


def get_price_values(user_string: str) -> Tuple[Optional[float], Optional[float]]:
    """
    Returns min price and max price parameters from user's string.
    Returns None, None if prices weren't found.

    :param user_string: user's string with prices from message.
    :type user_string: str
    :return: min and max price if it were found else None, None.
    :rtype: Tuple[Optional[float], Optional[float]]
    """

    price_min, price_max = None, None
    price_list = convert_to_float_list(user_string)
    if len(price_list) == 2:
        price_min, price_max = min(price_list), max(price_list)
    return price_min, price_max


def get_distance(user_string: str) -> Optional[float]:
    """
    Returns distance parameter from user's string.
    Returns None if distance wasn't found.

    :param user_string: user's string with distance from message.
    :type user_string: str
    :return: distance if distance was found else None.
    :rtype: Optional[float]
    """

    distance = None
    distance_list = convert_to_float_list(user_string)
    if len(distance_list) == 1:
        distance = distance_list[0]
    return distance


def convert_to_float_list(user_string: str) -> List[Optional[float]]:
    """
    Tries to convert user string to list with float values.

    :param user_string: string from user.
    :type user_string: str
    :return: list with float values
    :rtype: List[Optional[float]]
    """

    if "," in user_string:
        user_string = user_string.replace(",", ".")
    try:
        float_list = [float(i) for i in user_string.split()]
    except ValueError:
        return []
    else:
        return float_list


def check_button_callbacks_correctness(keyboard: InlineKeyboardMarkup, room: int) -> InlineKeyboardMarkup:
    """
    Rewrites adults keyboard buttons callbacks if it doesn't match the room.

    :param keyboard: adults keyboard with saved previous info.
    :type keyboard: InlineKeyboardMarkup
    :param room: current room in booking
    :type room: int
    :return: keyboard with correct callbacks.
    :rtype: InlineKeyboardMarkup
    """

    counter = 1
    if keyboard.keyboard[0][0].callback_data.endswith(str(room)):
        return keyboard
    for line in keyboard.keyboard:
        for button in line:
            button.callback_data = f"my_a{counter},{room}"
            counter += 1
    return keyboard

