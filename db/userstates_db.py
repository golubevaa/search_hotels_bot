"""
Creation and edition of user's state in DB (Vedis)
"""

from typing import Optional
from vedis import Vedis
import pickle
import codecs

db_name = 'db/user_states.dbv'


def update_user_state(user: 'UserRequest') -> None:
    """
    Writes user state to DB.

    :param user: User which will be written to DB.
    :type user: UserRequest
    :return: None
    """

    _id = str(user.user_id)
    pickled_user = codecs.encode(pickle.dumps(user), "base64").decode()
    with Vedis(db_name) as db:
        db[_id] = pickled_user


def get_user_state_from_db(user_id: int) -> Optional['UserRequest']:
    """
    Tries to find UserRequest instance in Vedis DB by their id.
    Returns UserRequest instance if it was found.

    :param user_id: id of UserRequest instance.
    :type user_id: int
    :return: UserRequest instance if it was found.
    """

    with Vedis(db_name) as db:
        try:
            user_instance = pickle.loads(codecs.decode(db[str(user_id)].decode().encode(), "base64"))
            return user_instance
        except KeyError:
            return False


def remove_user_state_from_db(user_id: int) -> None:
    """
    Tries to delete UserRequest instance from Vedis DB by their id.

    :param user_id: id of UserRequest instance.
    :type user_id: int
    :return: None
    """

    with Vedis(db_name) as db:
        try:
            del db[str(user_id)]
        except KeyError:
            return

