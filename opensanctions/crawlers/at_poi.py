from pprint import pprint  # noqa
from ftmstore.memorious import EntityEmitter
from normality import collapse_spaces
from datetime import datetime
import re

states = ["niederösterreich", "oberösterreich", "burgenland", "tirol", "vorarlberg", "wien", "salzburg", "kärnten",
          "steiermark"]
months = {"Januar": 1, "Februar": 2, "März": 3, "April": 4, "Mai": 5, "Juni": 6, "Juli": 7,
          "August": 8, "September": 9, "Oktober": 10, "November": 11, "Dezember": 12}


def _extract_social_media(html, person, context):
    sm = html.xpath('.//span[contains(@class,"pl-3")]')
    if not len(sm):
        context.log.info("No social media(span with class 'pl-3') found")
        return

    websites = []
    for a in sm[0].findall(".//a"):
        link = a.get("href")
        websites.append(link)
    person.add("website", websites)


def _extract_personal_websites(context, person, html):
    websites = html.find(".//div[@class='website']")
    if websites is None:
        context.log.info("No personal website found.")
        return

    urls = []
    for a in websites.findall(".//a"):
        urls.append(a["href"])
    person.add("website", urls)


def _extract_addresses(context, html, person):
    addresses = []

    for block in html.xpath('.//div[contains(@class,"adressItem")]'):
        streetAddress = _get_itemprop(context, block, "streetAddress")
        postalCode = _get_itemprop(context, block, "postalCode")
        addressLocality = _get_itemprop(context, block, "addressLocality")
        addresses.append(", ".join([streetAddress, postalCode, addressLocality]))

    person.add("address", addresses)


def _extract_img_src(html):
    img_el = html.xpath(".//img[@itemprop='image']")
    if len(img_el):
        return img_el[0].get("src")


def _extract_birth_date(raw_date):
    if not raw_date:
        return

    arr = collapse_spaces(raw_date).split(" ")
    # year
    if len(arr) == 1 and re.match("\d\d\d\d", raw_date):
        return raw_date
    elif len(arr) == 3:
        if arr[0].endswith("."):  # remove dot
            arr[0] = arr[0][:len(arr[0]) - 1]
        try:
            day, month, year = int(arr[0]), months[arr[1]], int(arr[2])
            if day is None or month is None:
                return year
            return datetime(day=day, month=month, year=year).isoformat()
        except ValueError:
            return None


def _make_party(context, data, emitter, html):
    party_name = collapse_spaces(data["party"])
    if party_name not in ["...", "parteilos"]:
        party = emitter.make("Organization")
        party_name = _get_itemprop(context, html, "memberOf")
        party.add("name", party_name)
        party.add("sourceUrl", "https://meineabgeordneten.at")
        party.add("topics", "pol.party")
        # Abbreviation
        party.add("alias", data["party"])
        party.add("country", "at")
        party.make_id("meineabgeordneten.at", party_name)
        return party


def _parse_single_date(date):
    match = re.search(r"(\d\d\.\d\d\.\d\d\d\d)", date)
    if match:
        date = match.group(1)
        return datetime.strptime(date, "%d.%m.%Y").isoformat()
    match = re.search(r"(\d\d\d\d)", date)
    if match:
        date = match.group(1)
        return datetime.strptime(date, "%Y").isoformat()
    if "?" in date:
        # meinabgeordneten.at uses "?" indicating null
        return None


def _convert_time_span(raw_time_span):
    raw_time_span = collapse_spaces(raw_time_span)
    if "seit" in raw_time_span.lower():
        # "seit" (since) indicates that there is no end time
        return _parse_single_date(raw_time_span), None
    elif "-" in raw_time_span:
        arr = raw_time_span.split("-")
        return _parse_single_date(arr[0]), _parse_single_date(arr[1])


def _extract_time_span(row):
    raw_time_span = row.xpath(".//span[@class='aktiv']")
    active = len(raw_time_span)
    if not active:
        raw_time_span = row.xpath(".//span[@class='inaktiv']")
    return active, raw_time_span


def _extract_state_name(description, prefix):
    match = re.search("(" + "|".join(states) + ")", description)
    if not match:
        return
    return prefix + " " + match.group(1).title()


def make_mandates(person, context, description, description_sub, startDate, endDate, emitter, org_website):
    # Information provided is not very well machine readable, but standardized in natural text.
    # Due to the valuable information, some basic text processing is being done.
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
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif re.match(r"bundesminister[in]?\sfür", description_lower):
        name = "Bundesregierung"
        organization.add("alias", ["Government of Austria", "Austrian Federal Government"])
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif re.match(r"abgeordneter?\szum\s?[^ ]*\slandtag", description_lower) \
            and "ersatzabgeordneter" not in description_lower:
        name = _extract_state_name(description_lower, "Landtag")
        if not name:
            return
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif "mitglied des bundesrates" in description_lower and \
            "ersatzmitglied" not in description_lower:
        name = "Bundesrat"
        organization.add("alias", "Federal Council")

        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif "volksanwalt" in description_lower \
            or "volksanwältin" in description_lower:
        name = "Volksanwaltschaft"
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif "landesrat" in description_lower or "landesrätin" in description_lower:
        name = _extract_state_name(description_lower, "Landesregierung")
        if not name:
            return
        membership.add("description", description)
        membership.add("summary", "Landesrat")
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)

    elif "bürgermeister" in description_lower:
        pass  # "von hall in tirol"

    elif "landeshauptmann" in description_lower:
        name = _extract_state_name(description_lower, "Landesregierung")
        if not name:
            return
        organization.add("name", name)
        if "stellvertreter" in description_lower:
            membership.add("summary", "Landeshauptmann Stellvertreter")
        else:
            membership.add("summary", "Landeshauptmann")
        _create_org_and_attach(emitter, context, organization, person, name, membership, description)


def _create_org_and_attach(emitter, context, organization, person, org_name, membership, description):
    organization.add("name", org_name)
    organization.make_id("meineabgeordneten.at", org_name)
    pprint(organization.to_dict())
    emitter.emit(organization)

    membership.add("member", person.id)
    membership.add("organization", organization.id)
    membership.add("description", description)
    membership.make_id(organization.id, person.id)
    # pprint(membership.to_dict())

    context.log.info("CREATED ORGANISATION '" + org_name + "' and membership with id '" + membership.id + "'")
    emitter.emit(membership)


def _parse_info_table(emitter, context, person, html, entity_maker, div_id):
    """ There are various "tables" that do contain information about mandates, societies or past jobs. This is the
    generic function that parses this information and calls a specific function that does the entity mapping. """

    summary = []
    descs = []

    # If field is "firmenfunktion" there is a special case (parse sub-companies)
    isWork = div_id == "firmenfunktionen"
    mandate_div = html.find(".//div[@id='{}']".format(div_id))
    if mandate_div is None:
        context.log.warning("No 'mandate' field found")
        return

    # complex match due to duplicated fields in DOM (displayed according to window size)
    for row in mandate_div.xpath(".//div[contains(@class,'funktionszeile') and contains(@class,'d-lg-none')]"):
        active, raw_time_span = _extract_time_span(row)

        if not len(raw_time_span):
            # this should not happen -> go to next iteration
            context.log.error("Did not find time span in mandates field")
            continue

        startDate, endDate = _convert_time_span(raw_time_span[0].text) or (None, None)
        # context.log.info("PARSED TIMESPAN: from " + (startDate or "none") + " to " + (endDate or "none"))

        description, description_sub, href, affiliated = _extract_table_description(context, row, isWork) or (
            None, None, None, None)
        if not description:
            continue

        if isWork:
            # special entity maker
            entity_maker(person, context, description, description_sub, startDate, endDate, emitter, href, affiliated)
        else:
            # generic entity maker
            entity_maker(person, context, description, description_sub, startDate, endDate, emitter, href)

        if active:
            summary.append(description)
        else:
            descs.append(raw_time_span[0].text + ": " + description)

    person.add("summary", summary)
    person.add("description", summary.extend(descs))


def _extract_table_description(context, row, isWork):
    description_sub_el = row.xpath(".//span[@class='bold']")
    affiliated = None

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

        if isWork:
            aff_div = desc_parent.xpath('.//div[contains(@class,"tochterfirmen")]')
            if len(aff_div):
                affiliated = aff_div[0]
                desc_parent.remove(affiliated)

        desc_sub = collapse_spaces(desc_parent.text_content())
        description = collapse_spaces(desc_main.text_content())
        context.log.info("PARSED MANDATE DESCRIPTION: {}, {}".format(description, desc_sub))
        return description, desc_sub, href, affiliated


def _make_societies(person, context, description, description_sub, startDate, endDate, emitter, org_website):
    organization = emitter.make("Organization")
    organization.add("website", org_website)
    membership = emitter.make("Membership")
    membership.add("startDate", startDate)
    membership.add("endDate", endDate)
    print("++++ SOCIETY ++++")
    _create_org_and_attach(emitter, context, organization, person, description, membership, description_sub)


def _make_work_and_affiliates(person, context, description, description_sub, startDate, endDate, emitter, org_website,
                              affiliates):
    company_owner = emitter.make("Company")
    company_owner.add("website", org_website)
    membership = emitter.make("Membership")
    membership.add("startDate", startDate)
    membership.add("endDate", endDate)

    _create_org_and_attach(emitter, context, company_owner, person, description, membership, description_sub)

    if affiliates is None:
        return

    for aff in affiliates.xpath('.//div[contains(@class,"tochterfirma")]'):
        aff_name_span = aff.xpath(".//span[@class='tochterFirmaName']")
        aff_url_span = aff.xpath('.//span[@class="tochterFirmaLink"]')
        aff_rel_span = aff.xpath('.//span[@class="tochterFirmaBeziehung"]')

        aff_name = collapse_spaces(aff_name_span[0].text) if len(aff_name_span) else None

        if not aff_name:
            # An affiliated company without a name indicates a parsing error
            continue

        _create_affiliated_company(aff_name, aff_rel_span, aff_url_span, company_owner, context, emitter)


def _create_affiliated_company(aff_name, aff_rel_span, aff_url_span, company_owner, context, emitter):
    aff_href = aff_url_span[0].find(".//a") if len(aff_url_span) else None
    aff_href = aff_href.get("href") if aff_href is not None else None
    aff_rel = aff_rel_span[0].text if len(aff_rel_span) else None

    company = emitter.make("Company")
    company.add("name", aff_name)
    company.add("website", aff_href)
    company.make_id("meineabgeordneten.at", aff_name)
    company_ownership = emitter.make("Ownership")
    if aff_rel:
        # info is given that way: GESELLSCHAFTER 50.00% (100.00...)
        match_percentage = re.search(r"(\d\d?\d?\.\d\d)", aff_rel)
        aff_pct = match_percentage.group(1) if match_percentage else None
        if aff_pct:
            aff_type = collapse_spaces(aff_rel[:match_percentage.start()])
        else:
            aff_type = collapse_spaces(aff_rel)

        print("AFFILIATE pct '{}' ownerType '{}'".format(aff_pct, aff_type))
        company_ownership.add("percentage", aff_pct)
        company_ownership.add("ownershipType", aff_type)

    company_ownership.add("owner", company_owner.id)
    company_ownership.add("asset", company.id)
    company_ownership.make_id(company_owner.id, company.id)
    emitter.emit(company)
    emitter.emit(company_ownership)
    context.log.info("CREATED COMPANY '" + aff_name + "' and membership with id '" + company_ownership.id + "'")
    # pprint(company.to_dict())
    # pprint(company_ownership.to_dict())


def _get_itemprop(context, html, prop, el="span"):
    # Basic metadata is stored in microdata tag.
    title = html.xpath(".//" + el + "[@itemprop='" + prop + "']")
    if len(title):
        return collapse_spaces(title[0].text)
    else:
        context.log.info("Property <span itemprop='" + prop + "'/> not found.")


def parse(context, data):
    url = data["url"]
    response = context.http.rehash(data)
    html = response.html
    emitter = EntityEmitter(context)

    person = emitter.make("Person")

    title = _get_itemprop(context, html, 'http://schema.org/honorificPrefix')
    firstName = _get_itemprop(context, html, "http://schema.org/givenName")
    familyName = _get_itemprop(context, html, "http://schema.org/familyName")

    if not firstName or not familyName:
        return

    context.log.info("Parsing Person '" + firstName + " " + familyName + "' found at: " + url)
    birthDate = _extract_birth_date(_get_itemprop(context, html, "birthDate"))
    birthPlace = _get_itemprop(context, html, "birthPlace")
    telephone = _get_itemprop(context, html, "http://schema.org/telephone")
    faxNumber = _get_itemprop(context, html, "http://schema.org/faxNumber")
    image = _extract_img_src(html)
    email = _get_itemprop(context, html, "http://schema.org/email", "*")
    _extract_personal_websites(context, person, html)

    person.add("title", title)
    person.add("firstName", firstName)
    person.add("lastName", familyName)
    person.add("name", " ".join([firstName, familyName]))
    person.add("birthDate", birthDate)
    person.add("birthPlace", birthPlace)
    person.add("country", "at")

    _extract_social_media(html, person, context)
    _extract_addresses(context, html, person)
    person.add("phone", telephone)
    person.add("email", email)
    person.add("sourceUrl", url)
    person.make_id(url, firstName, familyName, birthDate, birthPlace)

    _parse_info_table(emitter, context, person, html, make_mandates, "mandate")
    _parse_info_table(emitter, context, person, html, _make_societies, "vereine")
    _parse_info_table(emitter, context, person, html, _make_work_and_affiliates, "firmenfunktionen")

    party = _make_party(context, data, emitter, html)
    emitter.emit(person)

    if not party:
        emitter.finalize()
        return

    # pprint(party.to_dict())
    emitter.emit(party)

    membership = emitter.make("Membership")
    membership.make_id(person.id, party.id)
    membership.add("member", person.id)
    membership.add("organization", party.id)
    membership.add("sourceUrl", url)
    emitter.emit(membership)
    # pprint(person.to_dict())
    emitter.finalize()


def index(context, data):
    res = context.http.rehash(data)

    for abg_row in res.html.xpath('.//div[contains(@class,"abgeordneter")]'):
        url = abg_row.find(".//div//a").get("href")
        party = abg_row.find(".//span[@class='partei']")
        context.log.info("Crawling representative: %s", url)
        context.emit(data={"url": url, "party": party.text})
