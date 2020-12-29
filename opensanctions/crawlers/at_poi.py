from pprint import pprint  # noqa
from ftmstore.memorious import EntityEmitter
from normality import collapse_spaces
from datetime import datetime


def parse_social_media(html, person, context):
    sm = html.xpath('.//span[contains(@class,"pl-3")]')
    if not len(sm):
        context.log.info("No social media(span with class 'pl-3') found")
        return

    websites = []
    for a in sm[0].findall(".//a"):
        link = a.get("href")
        context.log.info(a.get("title") + ": " + link)
        websites.append(link)
    person.add("website", websites)


def parse_personal_websites(context, person, html):
    websites = html.find(".//div[@class='website']")
    if websites is None:
        context.log.info("No personal website.")
        return

    urls = []
    for a in websites.findall(".//a"):
        urls.append(a["href"])
    person.add("website", urls)


def parse_addresses(context, html, person):
    addresses = []

    for block in html.xpath('.//div[contains(@class,"adressItem")]'):
        streetAddress = get_itemprop(context, block, "streetAddress")
        postalCode = get_itemprop(context, block, "postalCode")
        addressLocality = get_itemprop(context, block, "addressLocality")
        addresses.append(", ".join([streetAddress, postalCode, addressLocality]))

    person.add("address", addresses)


def get_img_src(context, html):
    img_el = html.xpath(".//img[@itemprop='image']")
    if len(img_el):
        return img_el[0].get("src")
    else:
        context.log.info("No image found.")


def parse_date(context, raw_date):
    context.log.info("RAW DATE: " + raw_date)
    months = {"Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7,
              "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12}
    arr = collapse_spaces(raw_date).split(" ")
    if arr[0].endswith("."):  # remove dot
        arr[0] = arr[0][:len(arr[0]) - 1]
    day, month, year = int(arr[0]), months[arr[1]], int(arr[2])
    context.log.info("DATE PARSED: " + datetime(day=day, month=month, year=year).strftime("%m/%d/%Y"))
    return datetime(day=day, month=month, year=year).isoformat()


def parse_party(context, data, emitter, html):
    if data["party"] not in ["..."]:
        party = emitter.make("Organization")

        party_name = get_itemprop(context, html, "memberOf")
        party.add("name", party_name)
        party.add("sourceUrl", data["url"])
        party.add("topics", "pol.party")
        party.add("alias", data["party"])
        party.add("country", "at")
        party.make_id("meineabgeordneten.at", party_name)
        return party


def parse_time_span(raw_time_span):
    return collapse_spaces(raw_time_span) # TODO


def mandate_description_to_membership(description, aktiv):
    # not very well machine readable, but standardized in natural text
    description = description.lower()
    if "abgeordneter zum nationalrat" in description \
            and not "ersatzabgeordneter" in description:
        pass
    elif "abgeordneter zum landtag" in description\
            and not "ersatzabgeordneter" in description:
        pass # "tirol"
    # gemeinderat? Ersatzmitglied des Gemeinderates von Innsbruck, SPÖ
    elif "ööab" in description:
        pass
    elif "landesrat" in description:
        # steiermark
        # kann aber leider fehlen
        pass # "Landesrätin für Finanzen und Integration von ab 2013 auch Landesrätin für Frauen
    elif "bürgermeister" in description:
        pass # "von hall in tirol"
    elif "landeshauptmann" in description:
        pass #Landeshauptmann von Burgenland
    elif "präsident" in description:
        #Präsidentin des Landtages von Steiermark, SPÖ
        # achtung: Vizepräsident des Bundesrates
        pass



def parse_mandates(context, html, person):
    summary =[]
    descs = []

    mandate_div = html.find(".//div[@id='mandate']")
    for row in mandate_div.xpath(".//div[@class='row']"):
        raw_time_span = row.xpath(".//span[@class='aktiv']")
        active = len(raw_time_span)
        if not active:
            raw_time_span = row.xpath(".//span[@class='inaktiv']")

        if not len(raw_time_span):
            context.log.error("Did not find time span in mandates field")
            return
        time_span = parse_time_span(raw_time_span[0].text)
        context.log.info("PARSED TIMESPAN: " + time_span)

        description_sub_el = row.xpath(".//span[@class='bold']")
        if not len(description_sub_el):
            context.log.error("Did not find description in mandates field")
            return

        # sometimes text is wrapped inside <a ... />
        desc_parent = description_sub_el[0].getparent()
        if desc_parent.tag == "a":
            link = desc_parent.get("href")
            desc_parent= desc_parent.getparent()

        description = collapse_spaces(description_sub_el[0].getparent().text_content())
        context.log.info("PARSED MANDATE DESCRIPTION: " + description)

        if active:
            summary.append(description)
            mandate_description_to_membership(description)
        else:
            descs.append(time_span + ": " + description)

    person.add("summary", summary)
    person.add("description", summary.extend(descs))


def parse(context, data):
    url = data["url"]
    response = context.http.rehash(data)
    html = response.html
    emitter = EntityEmitter(context)

    person = emitter.make("Person")

    title = get_itemprop(context, html, 'http://schema.org/honorificPrefix')
    firstName = get_itemprop(context, html, "http://schema.org/givenName")
    familyName = get_itemprop(context, html, "http://schema.org/familyName")
    birthDate = parse_date(context, get_itemprop(context, html, "birthDate"))  # TODO parse date
    birthPlace = get_itemprop(context, html, "birthPlace")
    telephone = get_itemprop(context, html, "http://schema.org/telephone")
    faxNumber = get_itemprop(context, html, "http://schema.org/faxNumber")
    image = get_img_src(context, html)
    email = get_itemprop(context, html, "http://schema.org/email", "*")
    parse_personal_websites(context, person, html)

    person.add("title", title)
    person.add("firstName", firstName)
    person.add("lastName", familyName)
    person.add("birthDate", birthDate)
    person.add("birthPlace", birthPlace)
    parse_social_media(html, person, context)
    parse_addresses(context, html, person)
    person.add("phone", telephone)
    person.add("email", email)
    person.add("sourceUrl", url)
    parse_mandates(context, html, person)
    person.make_id(url, firstName, familyName, birthDate, birthPlace)

    party = parse_party(context, data, emitter, html)
    emitter.emit(party)

    membership = emitter.make("Membership")
    membership.make_id(person.id, party.id)
    membership.add("member", person)
    membership.add("organization", party)
    membership.add("sourceUrl", url)
    emitter.emit(membership)

    if len(data):
        context.log.info(pprint(data))

    emitter.finalize()

# TODO aufteilen von mandat parser in eigenen step?

def get_itemprop(context, html, prop, el="span"):
    title = html.xpath(".//" + el + "[@itemprop='" + prop + "']")
    if len(title):
        return collapse_spaces(title[0].text)
    else:
        context.log.info("Property <span itemprop='" + prop + "'/> not found.")


def index(context, data):
    res = context.http.rehash(data)

    for abg_row in res.html.xpath('.//div[contains(@class,"abgeordneter")]'):
        url = abg_row.find(".//div//a").get("href")
        party = abg_row.find(".//span[@class='partei']")
        context.log.info("Crawling representative: %s", url)
        context.emit(data={"url": url, "party": party.text})
