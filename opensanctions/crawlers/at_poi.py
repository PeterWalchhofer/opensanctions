from pprint import pprint  # noqa
from ftmstore.memorious import EntityEmitter
from normality import collapse_spaces
from datetime import datetime
import re

states = ["niederösterreich", "oberösterreich", "burgenland", "tirol", "vorarlberg", "wien", "salzburg", "kärnten",
            "steiermark"]
months = {"Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7,
          "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12}


def parse_social_media(html, person, context):
    sm = html.xpath('.//span[contains(@class,"pl-3")]')
    if not len(sm):
        context.log.info("No social media(span with class 'pl-3') found")
        return

    websites = []
    for a in sm[0].findall(".//a"):
        link = a.get("href")
        websites.append(link)
    person.add("website", websites)


def parse_personal_websites(context, person, html):
    websites = html.find(".//div[@class='website']")
    if websites is None:
        context.log.info("No personal website found.")
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


def parse_date(raw_date):
    try:
        if not raw_date:
            return

        arr = collapse_spaces(raw_date).split(" ")
        # year
        if len(arr) == 1 and re.match("\d\d\d\d", raw_date):
            return datetime.strptime("%Y", raw_date).isoformat()
        elif len(arr) == 3:
            if arr[0].endswith("."):  # remove dot
                arr[0] = arr[0][:len(arr[0]) - 1]
            day, month, year = int(arr[0]), months[arr[1]], int(arr[2])

            return datetime(day=day, month=month, year=year).isoformat()
    except:
        return None


def parse_party(context, data, emitter, html):
    if data["party"] not in ["...", "parteilos"]:
        party = emitter.make("Organization")

        party_name = get_itemprop(context, html, "memberOf")
        party.add("name", party_name)
        party.add("sourceUrl", "https://meineabgeordneten.at")
        party.add("topics", "pol.party")
        # Abbreviation
        party.add("alias", data["party"])
        party.add("country", "at")
        party.make_id("meineabgeordneten.at", party_name)
        return party


def match_date_format(date):
    match = re.search(r"(\d\d\.\d\d\.\d\d\d\d)", date)
    if match:
        date = match.group(1)
        return datetime.strptime(date, "%d.%m.%Y").isoformat()
    match = re.search(r"(\d\d\d\d)", date)
    if match:
        date = match.group(1)
        return datetime.strptime(date, "%Y").isoformat()
    if "?" in date:
        # meinabgeordneten uses "?" as null-variable
        return None


def convert_time_span(raw_time_span):
    raw_time_span = collapse_spaces(raw_time_span)  # TODO
    if "seit" in raw_time_span.lower():
        return match_date_format(raw_time_span), None
    elif "-" in raw_time_span:
        arr = raw_time_span.split("-")
        return match_date_format(arr[0]), match_date_format(arr[1])


def extract_state_name(description, prefix):
    match = re.search("(" + "|".join(states) + ")", description)
    if not match:
        return
    return prefix + " " + match.group(1).title()


def mandate_description_to_membership(person, context, description, description_sub, startDate, endDate, emitter, org_website):
    # Information provided is not very well machine readable, but standardized in natural text.
    # Due to the rich information, some natural text processing is being done
    organization = emitter.make("Organization")
    organization.add("website", org_website)
    organization.add("country", "at")
    membership = emitter.make("Membership")
    membership.add("startDate", startDate)
    membership.add("endDate", endDate)
    description = " ".join([description, description_sub])  # separation not needed here
    description_lower = description.lower()

    if re.match(r"abgeordneter? zum nationalrat", description_lower) \
            and not "ersatzabgeordneter" in description_lower:
        name = "Nationalrat"
        organization.add("alias", "National Council")

        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif re.match(r"bundesminister[in]?\sfür", description_lower):
        name = "Bundesregierung"
        organization.add("alias", ["Government of Austria", "Austrian Federal Government"])
        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif re.match(r"abgeordneter?\szum\s?[^ ]*\slandtag", description_lower) \
            and "ersatzabgeordneter" not in description_lower:
        name = extract_state_name(description_lower, "Landtag")
        if not name:
            return
        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif "mitglied des bundesrates" in description_lower and \
            "ersatzmitglied" not in description_lower:
        name = "Bundesrat"
        organization.add("alias", "Federal Council")

        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif "volksanwalt" in description_lower \
            or "volksanwältin" in description_lower:
        name = "Volksanwaltschaft"
        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif "ööab" in description_lower:
        pass

    elif "landesrat" in description_lower or "landesrätin" in description_lower:
        name = extract_state_name(description_lower, "Landesregierung")
        if not name:
            return
        membership.add("description", description)
        membership.add("summary", "Landesrat")
        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)

    elif "bürgermeister" in description_lower:
        pass  # "von hall in tirol"

    elif "landeshauptmann" in description_lower:
        name = extract_state_name(description_lower, "Landesregierung")
        if not name:
            return
        organization.add("name", name)
        if "stellvertreter" in description_lower:
            membership.add("summary", "Landeshauptmann Stellvertreter")
        else:
            membership.add("summary", "Landeshauptmann")
        createOrgaAndMemb(emitter, context, organization, person, name, membership, description)


def createOrgaAndMemb(emitter, context, organization, person, org_name, membership, description):
    organization.add("name", org_name)
    organization.make_id("meineabgeordneten.at", org_name)
    pprint(organization.to_dict())
    emitter.emit(organization)

    membership.add("member", person.id)
    membership.add("organization", organization.id)
    membership.add("description", description)
    membership.make_id(organization.id, person.id)
    pprint(membership.to_dict())

    context.log.info("CREATED ORGANISATION '" + org_name + "' and membership with id '" + membership.id + "'")
    emitter.emit(membership)


def parse_info_table(emitter, context, person, html, parser, div_id):
    summary = []
    descs = []

    mandate_div = html.find(".//div[@id='{}']".format(div_id))
    if mandate_div is None:
        context.log.warning("No 'mandate' field found")
        return

    # complex match due to duplicated fields in DOM (displayed according to window size)
    for row in mandate_div.xpath(".//div[contains(@class,'funktionszeile') and contains(@class,'d-lg-none')]"):
        active, raw_time_span = parse_time_span(row)

        if not len(raw_time_span):
            # this should not happen -> go to next iteration
            context.log.error("Did not find time span in mandates field")
            continue

        startDate, endDate = convert_time_span(raw_time_span[0].text) or (None, None)
        context.log.info("PARSED TIMESPAN: from " + (startDate or "none") + " to " + (endDate or "none"))

        description, description_sub, href = extract_description(context, row) or (None, None)
        if not description:
            continue

        parser(person, context, description, description_sub, startDate, endDate, emitter, href)
        if active:
            summary.append(description)
        else:
            descs.append(raw_time_span[0].text + ": " + description)

    person.add("summary", summary)
    person.add("description", summary.extend(descs))


def extract_description(context, row):
    description_sub_el = row.xpath(".//span[@class='bold']")
    if len(description_sub_el):
        # Description has a main part and a sub part.
        # The main part usually states the name of an organisation and
        # the sub part the function of the person in that organization.
        desc_main = description_sub_el[0]

        # sometimes text is wrapped inside <a ... /> that links to organization website
        desc_parent = desc_main.getparent()
        href = None

        if desc_parent.tag == "a":
            href = desc_parent.get("href")
            desc_parent.remove(desc_main)
            desc_parent = desc_parent.getparent()
        else:
            desc_parent.remove(desc_main)

        desc_sub = collapse_spaces(desc_parent.text_content())
        description = collapse_spaces(desc_main.text_content())
        context.log.info("PARSED MANDATE DESCRIPTION: {}, {}".format(description, desc_sub))
        return description, desc_sub, href


def parse_time_span(row):
    raw_time_span = row.xpath(".//span[@class='aktiv']")
    active = len(raw_time_span)
    if not active:
        raw_time_span = row.xpath(".//span[@class='inaktiv']")
    return active, raw_time_span


def parse_societies(person, context, description, description_sub, startDate, endDate, emitter, org_website):
    organization = emitter.make("Organization")
    organization.add("website", org_website)
    membership = emitter.make("Membership")
    membership.add("startDate", startDate)
    membership.add("endDate", endDate)
    print("++++ SOCIETY ++++")
    createOrgaAndMemb(emitter, context, organization, person, description, membership, description_sub)


def parse(context, data):
    url = data["url"]
    response = context.http.rehash(data)
    html = response.html
    emitter = EntityEmitter(context)

    person = emitter.make("Person")

    title = get_itemprop(context, html, 'http://schema.org/honorificPrefix')
    firstName = get_itemprop(context, html, "http://schema.org/givenName")
    familyName = get_itemprop(context, html, "http://schema.org/familyName")

    if not firstName or not familyName:
        return

    context.log.info("Parsing Person '" + firstName + " " + familyName + "' found at: " + url)
    birthDate = parse_date(get_itemprop(context, html, "birthDate"))
    birthPlace = get_itemprop(context, html, "birthPlace")
    telephone = get_itemprop(context, html, "http://schema.org/telephone")
    faxNumber = get_itemprop(context, html, "http://schema.org/faxNumber")
    image = get_img_src(context, html)
    email = get_itemprop(context, html, "http://schema.org/email", "*")
    parse_personal_websites(context, person, html)

    person.add("title", title)
    person.add("firstName", firstName)
    person.add("lastName", familyName)
    person.add("name", " ".join([firstName, familyName]))
    person.add("birthDate", birthDate)
    person.add("birthPlace", birthPlace)
    person.add("country", "at")

    parse_social_media(html, person, context)
    parse_addresses(context, html, person)
    person.add("phone", telephone)
    person.add("email", email)
    person.add("sourceUrl", url)
    person.make_id(url, firstName, familyName, birthDate, birthPlace)

    parse_info_table(emitter, context, person, html, mandate_description_to_membership, "mandate")
    parse_info_table(emitter, context, person, html, parse_societies, "vereine")

    party = parse_party(context, data, emitter, html)
    if not party:
        return
    pprint(party.to_dict())
    emitter.emit(party)

    membership = emitter.make("Membership")
    membership.make_id(person.id, party.id)
    membership.add("member", person)
    membership.add("organization", party)
    membership.add("sourceUrl", url)
    emitter.emit(membership)
    pprint(person.to_dict())
    emitter.emit(person)
    emitter.finalize()


def get_itemprop(context, html, prop, el="span"):
    # Basic metadata is stored in microdata tag.
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
