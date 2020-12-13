from pprint import pprint  # noqa
from ftmstore.dataset import Dataset
from ftmstore.settings import DATABASE_URI, DEFAULT_DATABASE_URI
from memorious.settings import DATASTORE_URI
import time
import random
import logging
from requests import RequestException
from typing import Dict
import os
ORIGIN = "memorious"
log = logging.getLogger(__name__)

# from https://github.com/alephdata/followthemoney-store/blob/f78d6a85360090d7859d36c8753be778bc7c723e/ftmstore/memorious.py
def get_dataset(context, origin=ORIGIN):
    name = context.get("dataset", context.crawler.name)
    origin = context.get("dataset", origin)
    # Either use a database URI that has been explicitly set as a
    # backend, or default to the memorious datastore.
    database_uri = DATABASE_URI
    if DATABASE_URI == DEFAULT_DATABASE_URI:
        database_uri = DATASTORE_URI
    return Dataset(name, database_uri=database_uri, origin=origin)




def ftm_load_dossier(context, data):
    """Write each entity from an ftm store to Dossier"""

    print(pprint(context))
    crawler_name = context.params.get("foreign_id", context.crawler.name)

    entities = get_dataset(context)
    chunk = []
    for entity in entities:
        if hasattr(entity, "to_dict"):
            entity = entity.to_dict()
        entity_origin = entity["origin"]
        if isinstance(entity_origin, list) and len(entity_origin):
            print("HALLO HELMUT")
            entity["origin"] = entity_origin[0]
        chunk.append(entity)

    #print(chunk)
    url = "http://" +  os.environ.get("GRAPH_DOSSIER_URI") + "/entities/"+crawler_name
    try:
        response = context.http.post(url, json=chunk, params=context.params)
        #response.raise_for_status()
    except RequestException as exc:
        raise exc



# def ftm_load_aleph(context, data):
#     """Write each entity from an ftm store to Aleph via the _bulk API."""
#     try:
#         from alephclient.memorious import get_api
#     except ImportError:
#         context.log.error("alephclient not installed. Skipping...")
#         return
#     api = get_api(context)
#     if api is None:
#         return
#     foreign_id = context.params.get("foreign_id", context.crawler.name)
#     collection = api.load_collection_by_foreign_id(foreign_id, {})
#     collection_id = collection.get("id")
#     unsafe = context.params.get("unsafe", False)
#     entities = get_dataset(context)
#     api.write_entities(collection_id, entities, unsafe=unsafe)