"""
Main scenario functions
"""

from src.scenario_models import *
from src.hotels_api import get_locale


@set_stage
def set_price(msg: Message) -> None:
    """
    Sets min and max price in bestdeal scenario.

    :param msg: message wth min and max price.
    :type msg: Message
    :return: None
    """

    user = UserRequest.get_user(msg.from_user.id)
    min_price, max_price = get_price_values(msg.text)
    if not min_price:
        user.cur_step = bot.send_message(text=bot_answers["wrong_format"],
                                         chat_id=user.user_id)
        bot.register_next_step_handler(user.cur_step, set_price)
    else:
        user.min_price, user.max_price = min_price, max_price
        min_price = int(min_price) if min_price % 1 == 0 else min_price
        max_price = int(max_price) if max_price % 1 == 0 else max_price
        bot.send_message(text=bot_answers["set_price"]["answer"].format(min_price, max_price),
                         chat_id=user.user_id)
        user.cur_step = bot.send_message(text=bot_answers["set_distance"]["question"],
                                         chat_id=user.user_id)
        bot.register_next_step_handler(user.cur_step, set_distance)


@set_stage
def set_distance(msg: Message) -> None:
    """
    Sets max distance from center in bestdeal scenario.

    :param msg: message with max distance.
    :type msg: Message
    :return: None
    """

    user = UserRequest.get_user(msg.from_user.id)
    distance = get_distance(msg.text)
    if not distance:
        user.cur_step = bot.send_message(text=bot_answers["wrong_format"],
                                         chat_id=user.user_id)
        bot.register_next_step_handler(user.cur_step, set_distance)
    else:
        user.distance = distance
        distance = int(distance) if distance % 1 == 0 else distance
        bot.send_message(text=bot_answers["set_distance"]["answer"].format(distance),
                         chat_id=user.user_id)
        user.cur_step = bot.send_message(text=bot_answers["photo"]["finish_main_messages_query_handler"],
                                         chat_id=user.user_id,
                                         reply_markup=DEF_KEYBOARDS["need_photo"])


@set_stage
def set_room_adults(user: UserRequest, room: Optional[int] = 0, edit: Optional[bool] = False) -> None:
    """
    Creates and sends a message to user with inline keyboard to choose number of adults in room.
    Starts user's guest cycle which specifies data filling of current room.
    This message will be used in a cycle of getting adults and children in current rooms.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    :param room: current room to specify (starts from 0)
    :type room: int
    :param edit: a flag to identify creation or edition of room
    :type edit: bool
    :return: None
    """

    text, keyboard = prepare_text_and_kb_to_adults_stage(user=user,
                                                         room=room,
                                                         edit=edit)
    user.cur_step = bot.send_message(chat_id=user.user_id,
                                     text=text,
                                     reply_markup=keyboard)


@set_stage
def set_room_children(user: UserRequest, room: int) -> None:
    """
    Creates and sends a message with inline keyboard to choose an age of current child in the room.
    Makes a pair "children{room}" = List[] in  UserRequest children dict if pair doesn't exist.
    Cause a handler to go to next room if children in room exceeds 6.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    :param room: current room to specify (starts from 0)
    :type room: int
    :return: None
    """

    text, keyboard = prepare_text_and_kb_to_children_stage(user=user,
                                                           room=room)
    user.cur_step = bot.send_message(text=text,
                                     chat_id=user.user_id,
                                     reply_markup=keyboard)


@set_stage
def ask_about_children(user: UserRequest, room: int) -> None:
    """
    Edit a message which was created in set_room_adults. Edit an inline keyboard to ask about children in the room.
    Clear value of UserRequest children dict related to current room.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    :param room: current room to specify (starts from 0)
    :type room: int
    :return: None
    """

    user.remove_children(room=room)

    keyboard = ScenarioKeyboards.ask_about_children_kb(room=room)
    text = bot_answers["ask_about_children"].format(room + 1)
    user.cur_step = bot.send_message(text=text,
                                     chat_id=user.user_id,
                                     reply_markup=keyboard)


@set_stage
@check_destination_cycle
def set_location(msg: Message) -> None:
    """
    Get a list of supposed locations.
    Creates and sends a message with inline keyboard to choose a location from list.
    Send a message with notification if location wasn't found.
    Call start function if any known command will be sent.

    :param msg: The message for which we want to handle new message in the same chat
    :type msg: telebot.types.Message
    :return: None
    """

    user = UserRequest.get_user(msg.from_user.id)

    if msg.text not in (*commands, *common_commands.keys()):
        user.start_search = msg
        supposed_locations = get_locale(city=msg.text)
        if supposed_locations:
            text = bot_answers["location"]["set_location"]
            keyboard = ScenarioKeyboards.generate_set_location_kb(locations=supposed_locations)
            user.start_search = bot.send_message(text=text,
                                                 chat_id=msg.from_user.id,
                                                 reply_markup=keyboard)
        else:
            text = bot_answers["location"]["backup"]
            msg = bot.send_message(text=text,
                                   chat_id=msg.from_user.id)
            user.start_search = False
            bot.register_next_step_handler(message=msg,
                                           callback=set_location)
    else:
        msg.content_type = "text"
        start(msg)
        return


@set_stage
def set_hotel_count(user: UserRequest) -> None:
    """
    Creates and sends a message with inline keyboard to choose a number of hotels in request.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    :return: None
    """

    user.cur_step = bot.send_message(text=bot_answers["hotel_count"]["set_hotel_count"],
                                     chat_id=user.user_id,
                                     reply_markup=DEF_KEYBOARDS["num_of_hotels"])


@set_stage
def set_check_in(user: UserRequest) -> None:
    """
    Creates and sends a message with inline keyboard-calendar to choose a check-in date.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    :return: None
    """

    calendar, step = build_calendar(user=user,
                                    _id=1)
    user.cur_step = bot.send_message(text=bot_answers["check_in"]["set_check_in"],
                                     chat_id=user.user_id,
                                     reply_markup=calendar)


@set_stage
def set_check_out(user: UserRequest) -> None:
    """
    Creates and sends a message with inline keyboard-calendar to choose a check-out date.

    :param user: Specifies the user who is making the request
    :type user: UserRequest
    """

    calendar, step = build_calendar(user=user,
                                    _id=2)
    user.cur_step = bot.send_message(text=bot_answers["check_out"]["set_check_out"],
                                     chat_id=user.user_id,
                                     reply_markup=calendar)


@bot.callback_query_handler(func=lambda call: call.data.startswith("id="))
@define_next_stage(set_hotel_count, "destination_id")
def define_destination_id(call: CallbackQuery) -> str:
    """
    Handler to identify location_name and destination_id for current request.
    user's main message will be defined as message_id from an incoming
    callback query if user.main_message is not defined
    Calls set_hotel_count if count of hotels is not defined for current request.

    :param call: The CallbackQuery from inline keyboard which was sent in set_location.
    :type call: CallbackQuery
    :return: id of destination city.
    :rtype: str
    """

    user = UserRequest.get_user(user_id=call.from_user.id)

    define_location_name(user=user, call=call)
    text, edit_markup = save_current_stage_main_message_info(call_markup=call.message.reply_markup,
                                                             user=user,
                                                             stage="location",
                                                             format_arg=user.location_name)
    bot.edit_message_text(text=text,
                          chat_id=call.message.chat.id,
                          message_id=call.message.message_id,
                          reply_markup=edit_markup)

    return call.data[3:]


@bot.callback_query_handler(func=lambda call: call.data.startswith("h="))
@define_next_stage(set_check_in, "hotel_count")
def define_hotel_count(call: CallbackQuery) -> str:
    """
    Handler to identify number of hotels to show.
    Add info about number of hotels to main message.
    Calls set_check_in if there's no check-in date for current request.

    :param call: The CallbackQuery from inline keyboard which was sent in set_hotel_count.
    :type call: CallbackQuery
    :return: count of hotels
    :rtype: str
    """

    user = UserRequest.get_user(user_id=call.from_user.id)

    text, edit_markup = save_current_stage_main_message_info(call_markup=call.message.reply_markup,
                                                             user=user,
                                                             stage="hotel_count",
                                                             format_arg=call.data[2:])
    bot.edit_message_text(text=text,
                          chat_id=user.user_id,
                          message_id=user.main_message,
                          reply_markup=edit_markup)

    delete_message_if_not_main(call.message.message_id, user.main_message, True,
                               chat_id=user.user_id,
                               message_id=call.message.message_id)
    return call.data[2:]


@bot.callback_query_handler(func=DetailedTelegramCalendar.func(calendar_id=1))
@define_next_stage(set_check_out, "check_in")
def define_check_in(call: CallbackQuery) -> date:
    """
    Handler to identify check-in date.
    Add info about check-in date to main message.
    Calls set_checkout if there's no check-out date for current request.
    Returns a check-in date.

    :param call: The CallbackQuery from inline keyboard which was sent in set_check_in.
    :type call: CallbackQuery
    :return: Date
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)

    result, key, step = build_calendar_callback(call_data=call.data,
                                                user=user,
                                                _id=1)
    if not result and key:
        text = msg_text_depends_on_msg_id(user=user,
                                          additional_text=bot_answers["check_in"]["set_check_in"],
                                          msg_id=call.message.message_id)
        bot.edit_message_text(text=text,
                              chat_id=user.user_id,
                              message_id=call.message.message_id,
                              reply_markup=key)
    elif result:
        text, edit_markup = save_current_stage_main_message_info(call_markup=None,
                                                                 call_text=call.data,
                                                                 user=user,
                                                                 stage="check_in",
                                                                 format_arg=result)
        bot.edit_message_text(text=text,
                              chat_id=call.message.chat.id,
                              message_id=user.main_message,
                              reply_markup=edit_markup)

        delete_message_if_not_main(call.message.message_id, user.main_message, True,
                                   chat_id=user.user_id,
                                   message_id=call.message.message_id)
        return result


@bot.callback_query_handler(func=DetailedTelegramCalendar.func(calendar_id=2))
@define_next_stage(set_room_adults, "check_out")
def define_check_out(call: CallbackQuery) -> date:
    """
    Handler to identify check-out date.
    Add info about check-out date to main message.
    Calls set_room_adults for room 1 if there's no room for current booking.

    :param call: The CallbackQuery from inline keyboard which was sent in set_check_out.
    :type call: CallbackQuery
    :return: check out date
    :rtype: date
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)

    result, key, step = build_calendar_callback(call_data=call.data,
                                                user=user,
                                                _id=2)
    if not result and key:
        text = msg_text_depends_on_msg_id(user=user,
                                          additional_text=bot_answers["check_out"]["set_check_out"],
                                          msg_id=call.message.message_id)
        bot.edit_message_text(text=text,
                              chat_id=user.user_id,
                              message_id=call.message.message_id,
                              reply_markup=key)
    elif result:
        text, edit_markup = save_current_stage_main_message_info(call_markup=None,
                                                                 call_text=call.data,
                                                                 user=user,
                                                                 stage="check_out",
                                                                 format_arg=result)
        bot.edit_message_text(text=text,
                              chat_id=call.message.chat.id,
                              message_id=user.main_message,
                              reply_markup=edit_markup)

        delete_message_if_not_main(call.message.message_id, user.main_message, True,
                                   chat_id=user.user_id,
                                   message_id=call.message.message_id)
        return result


@bot.callback_query_handler(func=lambda call: call.data.startswith("my_a"))
def define_room_adults(call: CallbackQuery) -> None:
    """
    Handler to identify number of adults in rooms.
    user's main rooms message will be defined as message_id from an incoming
    callback query if user.main_rooms_message is not defined
    Calls ask_about_children for current room.

    :param call: The CallbackQuery from inline keyboard which was sent in set_room_adults.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)
    adults_in_room, room = [int(i) for i in call.data[4:].split(",")]

    if not user.main_rooms_message:
        user.main_rooms_message = call.message.message_id

    text = add_adults_info_to_user_memory(user=user,
                                          call_markup=call.message.reply_markup,
                                          format_arg=str(adults_in_room),
                                          room=room)
    bot.edit_message_text(text=text,
                          chat_id=user.user_id,
                          message_id=user.main_rooms_message)

    delete_message_if_not_main(call.message.message_id, user.main_rooms_message, True,
                               chat_id=user.user_id,
                               message_id=call.message.message_id)
    ask_about_children(user=user,
                       room=room)


@bot.callback_query_handler(func=lambda call: call.data.startswith("+") or call.data.startswith("-"))
def define_ask_about_children(call: CallbackQuery) -> None:
    """
    Handler to identify presence of children in the room.
    In cases of positive call.data (+):
        Calls set_room_children for current room.

    In cases of negative call.data (-):
        Ends user's guest cycle for current room.
        Adds info about children in current room to main rooms message.
        Modify inline keyboard in main room message to manage rooms in booking.


    :param call: The CallbackQuery from inline keyboard which was sent in set_room_adults.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)
    room = int(call.data[2:])

    if call.data.startswith("+"):
        delete_message_if_not_main(call.message.message_id, user.main_message, True,
                                   chat_id=user.user_id,
                                   message_id=call.message.message_id)
        set_room_children(user=user,
                          room=room)

    else:
        text, children_in_room = add_children_info_to_user_memory(user=user,
                                                                  room=room,
                                                                  disable_guest_cycle=True)
        markup = ScenarioKeyboards.generate_edit_rooms_kb(user_adults=len(user.adults))

        bot.edit_message_text(text=text,
                              chat_id=user.user_id,
                              message_id=user.main_rooms_message,
                              reply_markup=markup)
        additional_bool = children_in_room != 6
        delete_message_if_not_main(call.message.message_id, user.main_rooms_message, additional_bool,
                                   chat_id=user.user_id,
                                   message_id=call.message.message_id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("ch_age="))
def define_room_children(call: CallbackQuery) -> None:
    """
    Handler to identify age of current child in room.
    Adds info about children in current room to main rooms message.
    Calls set_room_children for current room if there's < 6 children in room.
    Calls define_ask_about_children with negative call data if children in room exceeds 6.

    :param call: The CallbackQuery from inline keyboard which was sent in set_children.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)

    age, room = [int(i) for i in call.data[7:].split(",")]
    user.add_child(age=age,
                   room=room)
    text, children_in_room = add_children_info_to_user_memory(user=user,
                                                              room=room,
                                                              disable_guest_cycle=False)

    bot.delete_message(chat_id=user.user_id,
                       message_id=call.message.message_id)

    bot.edit_message_text(text=text,
                          chat_id=user.user_id,
                          message_id=user.main_rooms_message)

    if children_in_room < 6:
        set_room_children(room=room,
                          user=user)
    else:
        call.data = f"-,{room}"
        define_ask_about_children(call)


@bot.callback_query_handler(func=lambda call: call.data.startswith("change"))
def edit_main_rooms_message(call: CallbackQuery) -> None:
    """
    Handler to manage all changes from main_rooms_message inline keyboards.
    Handles all callbacks which data starts with 'change'.
    Generate next step keyboards to modify data in booking.

    :param call: The CallbackQuery from inline keyboard of main_rooms_message.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)

    if call.data == "change_room":
        markup = ScenarioKeyboards.generate_edit_rooms_prev_data_kb(user)

    elif call.data == "change_new_room":
        if send_answer_callback_query_rooms_stage(call):
            return
        set_room_adults(user=user,
                        room=user.total_room,
                        edit=False)
        markup = ScenarioKeyboards.generate_edit_rooms_kb(user.total_room + 1)
        if len(call.message.reply_markup.keyboard) == len(markup.keyboard):
            return

    elif match(r"change_\d_room", call.data):
        edit_room = int(call.data[7])
        if send_answer_callback_query_rooms_stage(call,  edit_room + 1):
            return
        markup = ScenarioKeyboards.generate_edit_rooms_kb(user.total_room + 1)
        set_room_adults(user=user,
                        room=edit_room,
                        edit=True)

    elif call.data == "change_delete":
        markup = ScenarioKeyboards.generate_delete_rooms_kb(total_rooms=user.total_room)

    elif match(r"change_d\d_room", call.data):
        del_room = int(call.data[8])
        if send_answer_callback_query_rooms_stage(call,  del_room + 1):
            return
        delete_room(user=user, room=del_room)
        markup = ScenarioKeyboards.generate_edit_rooms_kb(user.total_room)
        text = generate_main_message_text(user_memory=user.memory["rooms"],
                                          without_rooms=False)

        bot.edit_message_text(text=text,
                              chat_id=user.user_id,
                              message_id=user.main_rooms_message,
                              reply_markup=markup)
        return

    elif call.data == "change_back":
        if call.message.message_id == user.main_message:
            markup = DEF_KEYBOARDS["main_changes"]
        elif call.message.message_id == user.main_rooms_message:
            markup = ScenarioKeyboards.generate_edit_rooms_kb(len(user.adults))

    bot.edit_message_reply_markup(chat_id=user.user_id,
                                  message_id=call.message.message_id,
                                  reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data in ("location", "hotel_count",
                                                            "check_in", "check_out", "main"))
def edit_main_message(call: CallbackQuery) -> None:
    """
    Handler to modify all info in main message.

    :param call: The CallbackQuery from inline keyboard of main_message.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)
    text, markup = get_main_message_text_and_markup(call_data=call.data,
                                                    msg_id=call.message.message_id,
                                                    user=user)

    bot.edit_message_text(text=text,
                          chat_id=user.user_id,
                          message_id=user.main_message,
                          reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data == "finish")
def finish_main_messages_query_handler(call: CallbackQuery) -> None:
    """
    Handler to finish filling info in main message and main rooms message.
    Makes a review of user's info.
    In positive results of review:
        Sends a message to ask about photos in response. Removes all inline keyboards used in this search.
    In negative results of review:
        Sends answer_callback_query with warnings to correct.


    :param call: The CallbackQuery from inline keyboard of main_rooms_message to start the search.
    :type call: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)
    warnings = check_booking_for_correctness(user=user)

    if warnings:
        bot.answer_callback_query(callback_query_id=call.id,
                                  text=warnings)
    else:
        for msg in (user.main_message, user.main_rooms_message):
            remove_keyboard(chat_id=user.user_id, msg_id=msg)

        user.main_message, user.main_rooms_message = None, None
        if user.command != "/bestdeal":
            user.cur_step = bot.send_message(text=bot_answers["photo"]["finish_main_messages_query_handler"],
                                             chat_id=user.user_id,
                                             reply_markup=DEF_KEYBOARDS["need_photo"])
            return
        msg = bot.send_message(text=bot_answers["set_price"]["question"],
                               chat_id=user.user_id)
        bot.register_next_step_handler(msg, set_price)


@bot.callback_query_handler(func=lambda call: call.data.startswith("photo"))
def go_to_searching(call: CallbackQuery) -> None:
    """
    Handles callbacks related to presence of photo in response.
    Starts the searching after filling required data

    :param call: The CallbackQuery from inline keyboard of messages with
        questions about hotels photos.
    :type: CallbackQuery
    :return: None
    """

    user = UserRequest.get_user(user_id=call.message.chat.id)

    if call.data.endswith("+"):
        bot.delete_message(chat_id=user.user_id,
                           message_id=call.message.message_id)
        user.cur_step = bot.send_message(text=bot_answers["photo"]["go_to_searching"],
                                         chat_id=user.user_id,
                                         reply_markup=DEF_KEYBOARDS["need_photo_true"])
    else:
        user.define_need_photo(call_data=call.data)
        bot.delete_message(chat_id=user.user_id,
                           message_id=call.message.message_id)
        bot.send_message(text=bot_answers["search_and_res"]["go_to_searching"],
                         chat_id=user.user_id)
        user.cur_step = None
        show_hotels_info(user=user)


@bot.message_handler(func=lambda message: message.text in (*common_commands.keys(), *commands)
                     or match(r"\b[Пп]ривет.*\b", message.text))
def start(message: Message) -> None:
    """
    Handles known commands and greetings messages.

    :param message: user's message with known command or greeting.
    :type message: Message
    :return: None
    """

    user = UserRequest.get_user(user_id=message.from_user.id)

    if message.text in common_commands.keys():
        bot.send_message(text=common_commands[message.text],
                         chat_id=user.user_id)

    elif match(r"\b[Пп]ривет.*\b", message.text):
        bot.send_message(text=common_commands["/start"],
                         chat_id=user.user_id)

    elif message.text in commands:
        if message.text == "/history":
            send_history(user)
        else:
            user = prepare_instance_to_new_search(user=user, new_command=message.text)
            msg = bot.send_message(text=bot_answers["location"]["start"],
                                   chat_id=user.user_id)
            bot.register_next_step_handler(message=msg,
                                           callback=set_location)


@bot.message_handler(content_types=["text"])
@check_destination_cycle
def route_to_correct_func(message: Message) -> None:
    """
    Handles all text messages except known commands and greetings.
    Tries to route messages to right function.
    In negative cases sends a message that it does not recognize the command.

    :param message: user's message
    :type message: Message
    :return: None
    """

    user = UserRequest.get_user(user_id=message.from_user.id)

    if stages[user.stage] in (0, 1):
        if user.command in commands:
            if not user.start_search:
                set_location(message)
                return
            return
    if stages[user.stage] >= 6 and user.command == "/bestdeal":
        if match(r"\b\d+ \d+\b", message.text):
            set_price(message)
            return
    if stages[user.stage] > 7:
        if convert_to_float_list(message.text) and len(convert_to_float_list(message.text)) == 1:
            set_distance(message)
            return
    bot.send_message(text=bot_answers["unknown"],
                     chat_id=user.user_id)


if __name__ == '__main__':
    bot.infinity_polling(timeout=125)
