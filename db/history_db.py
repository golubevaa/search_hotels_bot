"""
Saves and shows searching results (SQLite). Implementation of /history command.
"""

from sqlalchemy import create_engine, Table, MetaData, Column, Integer, DateTime, String
from sqlalchemy.orm import sessionmaker, mapper
from typing import List, Optional
from datetime import datetime
from src.bot_text import history_dict, hotels_link

engine = create_engine("sqlite:///db/history.db",
                       connect_args={"check_same_thread": False})
Session = sessionmaker(bind=engine)
session = Session()

metadata = MetaData(bind=engine)

history = Table("history", metadata,
                Column(name="id", type_=Integer,
                       primary_key=True, unique=True,
                       autoincrement=True, nullable=False),
                Column(name="telegram_id", type_=Integer, nullable=False),
                Column(name="date", type_=DateTime, nullable=False),
                Column(name="command", type_=String, nullable=False),
                Column(name="hotel", type_=String, nullable=False),
                Column(name="location", type_=String, nullable=False))


class History:
    """
    Class to working with DB. Args is columns in 'history' table which
    keeps info related to users queries.

    Args:
        :telegram_id (int):   telegram id of user which made request
            (same as UserRequest.user_id).
        :date (DateTime):   request's date and time.
        :hotel (List[str]):   will be got from list with strings.
            Every string is a concatenation of hotel id and hotel name.
            Up to 10 elements in list. hotel_format method concatenates
            all elements in list to string.
        :command (str):   the command which was sent to bot in query which results
            are pushed to DB.
    """

    def __init__(self, telegram_id, date, hotel, command, location):
        self.telegram_id: int = telegram_id
        self.date: DateTime = date
        self.command: str = command
        self.hotel: str = History.hotel_format(hotel=hotel)
        self.location: str = location

    @classmethod
    def hotel_format(cls, hotel: List[str]) -> str:
        """
        Method to concatenate strings 'hotel_id***hotel_name'
        to common string which will be pushed to DB (hotel column)

        :param hotel: list with strings 'hotel_id***hotel_name'
        :type hotel: List[str]
        :return: string with all 'hotel_id***hotel_name' passed pairs separated by '^&'
        :rtype: str
        """

        return "^&".join(hotel)

    def prepare_hotel_links(self):
        """
        Creates hotels links for telegram messages with MARKDOWN parse mode.

        :return: string with hotel links and hotels names from DB row.
        :rtype: str
        """

        links = []
        list_hotels = self.hotel.split("^&")
        for res in list_hotels:
            hotel_id, hotel_name = res.split("***")
            links.append(f"[{hotel_name}]({hotels_link['link']}{hotel_id}/)\n")
        return links

    def __repr__(self):
        return f"{self.telegram_id}; {self.date}; {self.hotel}"


mapper(History, history)
metadata.create_all(bind=engine)


def get_from_db(telegram_id: int) -> List[str]:
    """
    Makes a SELECT query to 'history' table. Get a list of History
    instances and prepares texts for telegram messages.

    :param telegram_id: telegram id of user making the request.
        Same as UserRequest.user_id
    :type: telegram_id: int
    :return: the list with prepared text for telegram messages
        with data about previous searches
    :rtype: List[Optional[str], ...]
    """

    result = []
    history_log: List[Optional[History]] = session.query(History).filter(
        History.telegram_id == telegram_id).all()
    if history_log:
        for history_item in history_log:
            result.append(prepare_message_text(history_item))
    return result


def push_to_db(telegram_id: int, date: datetime, hotel: List[str], command: str, location: str) -> None:
    """
    Creates an INSERT query into 'history' table. Creates a row with info about
    last user search.

    :param telegram_id: telegram_id: telegram id of user making the request.
        Same as UserRequest.user_id.
    :type: telegram_id: int
    :param date: last search's date and time.
    :type: date: datetime
    :param hotel: the string 'hotel_id1***hotel_name1^&hotel_id2***hotel_name2'
        with all hotels from last search.
    :type hotel: str
    :param command: the command which was sent to bot in query which results
            are pushed to DB (UserRequest.command).
    :param location: location name
    :type location: str
    :type command: str
    :return: None
    """

    new_history_item = History(telegram_id=telegram_id,
                               date=date,
                               hotel=hotel,
                               command=command,
                               location=location)
    session.add(new_history_item)
    session.commit()


def prepare_message_text(history_instance: History) -> str:
    """
    Prepares text for bot message relates to /history command.

    :param history_instance: data from 'history' table which presented
        as History instance.
    :type history_instance: History
    :return: the text ready to be sent. Contains all data about single query.
    :rtype: str
    """

    result = ""
    result += f"{history_instance.location}\n"
    result += f"{history_dict['datetime']} {history_instance.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
    result += f"{history_dict['command']} {history_instance.command}\n\n"
    for string in history_instance.prepare_hotel_links():
        result += string
    return result
