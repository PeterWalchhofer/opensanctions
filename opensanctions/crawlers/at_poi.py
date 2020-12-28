from pprint import pprint  # noqa
from ftmstore.memorious import EntityEmitter
from bs4 import BeautifulSoup


def parse_node(emitter, node):
    mep_id = node.findtext(".//id")
    person = emitter.make("Person")
    person.make_id("EUMEP", mep_id)
    name = node.findtext(".//fullName")
    person.add("name", name)
    url = "http://www.europarl.europa.eu/meps/en/%s" % mep_id
    person.add("sourceUrl", url)
    # first_name, last_name = split_name(name)
    # person.add("firstName", first_name)
    # person.add("lastName", last_name)
    person.add("nationality", node.findtext(".//country"))
    person.add("topics", "role.pep")
    emitter.emit(person)

    party_name = node.findtext(".//nationalPoliticalGroup")
    if party_name not in ["Independent"]:
        party = emitter.make("Organization")
        party.make_id("nationalPoliticalGroup", party_name)
        party.add("name", party_name)
        party.add("country", node.findtext(".//country"))
        emitter.emit(party)
        membership = emitter.make("Membership")
        membership.make_id(person.id, party.id)
        membership.add("member", person)
        membership.add("organization", party)
        emitter.emit(membership)

    group_name = node.findtext(".//politicalGroup")
    group = emitter.make("Organization")
    group.make_id("politicalGroup", group_name)
    group.add("name", group_name)
    group.add("country", "eu")
    emitter.emit(group)
    membership = emitter.make("Membership")
    membership.make_id(person.id, group.id)
    membership.add("member", person)
    membership.add("organization", group)
    emitter.emit(membership)


def parse_social_media(soup, person, context):
    sm = soup.select(".pl-3")
    if not len(sm):
        return

    # es kann zwei facebook links geben
    for a in sm[0].find_all("a"):
        link = a["href"]
        context.log.info(a["title"] + ": " + link)
        # person.add() TODO


def parse_personal_websites(soup, person):
    websites = soup.select(".websites")
    if not len(websites):
        return

    urls = []
    for a in websites[0].find_all("a"):
        urls.append(a["href"])
    person.add("website", urls)


def parse_adresses(soup, person):
    addresses = []
    for block in soup.select(".adresseItem.mb-3"):
        streetAddress = block.find("span", itemprop="streetAddress")
        postalCode = block.find("span", itemprop="postalCode")
        addressLocality = block.find("span", itemprop="addressLocality")
        addresses.append(", ".join([streetAddress, postalCode, addressLocality]))
    person.add("address", addresses)


def parse(context, data):
    url = data["url"]
    response = context.http.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    emitter = EntityEmitter(context)

    person = emitter.make("Person")
    # person.make_id("EUMEP", mep_id)  # TODO

    title = getItemprop(response)
    context.log.info("XPATH " + title.text)
    person.add("title", title.text)

    firstName = soup.find("span", itemprop="http://schema.org/givenName")
    person.add("firstName", firstName)

    familyName = soup.find("span", itemprop="http://schema.org/familyName")
    person.add("familyName", familyName)

    birthDate = soup.find("span", itemprop="birthDate")
    person.add("birthDate", birthDate)

    birthPlace = soup.find("span", itemprop="birthPlace")
    person.add("birthPlace", birthPlace)

    print("WHUUP \n " + birthDate.getText())
    parse_social_media(soup, person, context)

    parse_adresses(soup, person)

    telephone = soup.find_all("span", itemprop="http://schema.org/telephone")
    faxNumber = soup.find_all("span", itemprop="http://schema.org/faxNumber")
    person.add("telephone", telephone)

    email = soup.find_all("span", itemprop="http://schema.org/email")
    person.add("email", email)

    parse_personal_websites(soup, person)
    emitter.finalize()


def getItemprop(html, prop):
    title = html.find(".//span[@itemprop='" + prop + "']")
    if title:
        return title.text


def index(context, data):
    res = context.http.rehash(data)

    for abg_row in res.html.xpath('.//div[contains(@class,"abgeordneter")]//div//a'):
        url = abg_row.get("href")
        context.log.info("Crawling representative: %s", url)
        context.emit(data={"url": url})
