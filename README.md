# Fork
This is a fork from [OpenSanctions](https://github.com/pudo/opensanctions) as the project has been refactored, which would break the scraper that can be found at `opensanctions/crawlers/at_poi.py`.
To run the crawler, follow the instructions below. The UI unfortunately does not work, but the framework can be run headlessly. The scraper should start automatically when running docker-compose.

# OpenSanctions

The scrapers are executed using [memorious](https://github.com/alephdata/memorious),
a scraping framework.

## Running

1. Bring up the services:

        docker-compose up

2. Open a shell in the worker container:

        docker-compose exec worker sh

3. Run a crawler:

        memorious run at_poi

4. Export to CSVs:

        ftm store iterate -d at_poi | ftm export-csv


## Pushing data into Aleph

To push crawled entities to Aleph, add `ALEPHCLIENT_HOST` and `ALEPHCLIENT_API_KEY` as environment variables to the worker container and rerun the crawlers. Scraped entities are pushed to Aleph after a crawler is finished running.

You can also push crawled entities to Aleph manually.

1. Open a shell in worker container:

       docker-compose exec worker sh

2. Iterate over scraped entities

       ftm store iterate -d at_poi | alephclient write-entities -f at_poi
