import requests
import time
from test_items_eve_online import items_eve


# https://www.adam4eve.eu/info_locations.php


start_time = time.time()


def get_item_prices(item_id, item_name, region_id, region_name, station_id, station_name, sales_tax):
    url = "https://esi.evetech.net/latest/markets/{}/orders/?datasource=tranquility&order_type=all&page=1&type_id={}"

    headers = {
        'User-Agent': 'your_user_agent'
    }

    prices = {}

    region_url = url.format(region_id, item_id)
    response = requests.get(region_url, headers=headers)

    if response.status_code == 200:
        orders = response.json()

        filtered_orders = [order for order in orders if order["location_id"] == station_id]

        sell_prices = [order["price"] for order in filtered_orders if order["is_buy_order"] is False]
        buy_prices = [order["price"] for order in filtered_orders if order["is_buy_order"] is True]

        min_sell_price = min(sell_prices) if sell_prices else None
        max_buy_price = max(buy_prices) if buy_prices else None

        trade_volume = sum(order["volume_remain"] for order in filtered_orders if not order["is_buy_order"])

        if min_sell_price is not None and max_buy_price is not None:
            buy_price = min_sell_price
            profit_sell = buy_price - max_buy_price
            profit_sell_percentage = (profit_sell / buy_price) * 100

            prices[station_id] = {
                "region_name": region_name,
                "station_name": station_name,
                "item_name": item_name,
                "min_sell_price": min_sell_price,
                "max_buy_price": max_buy_price,
                "trade_volume": trade_volume,
                "profit_sell": profit_sell,
                "profit_sell_percentage": profit_sell_percentage
            }

    else:
        print(f"Ошибка при получении цен на товар '{item_name}' в регионе '{region_name}': {response.status_code}")

    return prices


items = [
    ### Ships
    ## Frigates
    # Frigates Amarr
    {"id": 2161, "name": "Crucifier"},
    {"id": 589, "name": "Executioner"},
    {"id": 590, "name": "Inquisitor"},
    {"id": 29248, "name": "Magnate"},
    {"id": 597, "name": "Punisher"},
    {"id": 591, "name": "Tormentor"},
    {"id": 37453, "name": "Crucifier Navy Issue"},
    {"id": 17703, "name": "Imperial Navy Slicer"},
    {"id": 72907, "name": "Magnate Navy Issue"},
    {"id": 11393, "name": "Retribution"},
    {"id": 11365, "name": "Vengeance"},
    {"id": 11188, "name": "Anathema"},
    {"id": 12038, "name": "Purifier"},
    {"id": 11190, "name": "Sentinel"},
    {"id": 11184, "name": "Crusader"},
    {"id": 11186, "name": "Malediction"},
    {"id": 37457, "name": "Deacon"},

    # Frigates Caldari
    {"id":582, "name": "Bantam"},
    {"id":583, "name": "Condor"},
    {"id":584, "name": "Griffin"},
    {"id":605, "name": "Heron"},
    {"id":602, "name": "Kestrel"},
    {"id":603, "name": "Merlin"},
    {"id":17619, "name": "Caldari Navy Hookbill"},
    {"id":37455, "name": "Griffin Navy Issue"},
    {"id":72904, "name": "Heron Navy Issue"},
    {"id":11381, "name": "Harpy"},
    {"id":11379, "name": "Hawk"},
    {"id":11192, "name": "Buzzard"},
    {"id":12032, "name": "Manticore"},
    {"id":11194, "name": "Kitsune"},
    {"id":11176, "name": "Crow"},
    {"id":11178, "name": "Raptor"},
    {"id":37458, "name": "Kirin"},

    # Frigates Gallente
    {"id":608, "name": "Atron"},
    {"id":607, "name": "Imicus"},
    {"id":594, "name": "Incursus"},
    {"id":609, "name": "Maulus"},
    {"id":592, "name": "Navitas"},
    {"id":593, "name": "Tristan"},
    {"id":17841, "name": "Federation Navy Comet"},
    {"id":72913, "name": "Imicus Navy Issue"},
    {"id":37456, "name": "Maulus Navy Issue"},
#    {"id":33677, "name": "Police Pursuit Comet"},
    {"id":12044, "name": "Enyo"},
    {"id":12042, "name": "Ishkur"},
    {"id":11172, "name": "Helios"},
    {"id":11377, "name": "Nemesis"},
    {"id":11174, "name": "Keres"},
    {"id":11202, "name": "Ares"},
    {"id":11200, "name": "Taranis"},
    {"id":37459, "name": "Thalia"},

    # Frigates Minmatar
    {"id":598, "name": "Breacher"},
    {"id":599, "name": "Burst"},
    {"id":586, "name": "Probe"},
    {"id":587, "name": "Rifter"},
    {"id":585, "name": "Slasher"},
    {"id":3766, "name": "Vigil"},
    {"id":72903, "name": "Probe Fleet Issue"},
    {"id":17812, "name": "Republic Fleet Firetain"},
    {"id":37454, "name": "Vigil Fleet Issue"},
    {"id":11400, "name": "Jaguar"},
    {"id":11371, "name": "Wolf"},
    {"id":11182, "name": "Cheetah"},
    {"id":12034, "name": "Hound"},
    {"id":11387, "name": "Hyena"},
    {"id":11196, "name": "Claw"},
    {"id":11198, "name": "Stiletto"},
    {"id":37460, "name": "Scalpel"},

    # Frigate Triglavian
    {"id":47269, "name": "Damavik"},
    {"id":52250, "name": "Nergal"},

    # Frigates EDENCOM
    {"id":54731, "name": "Skybreaker"},

    # Frigate Pirate Faction
    {"id":33468, "name": "Astero"},
    {"id":17926, "name": "Cruor"},
    {"id":17928, "name": "Daredevil"},
    {"id":17932, "name": "Dramiel"},
    {"id":33816, "name": "Garmur"},
    {"id":17924, "name": "Succubus"},
    {"id":17930, "name": "Worm"},

    # Frigates Special Edition
    {"id":3532, "name": "Echelon"},
    {"id":11940, "name": "Gold Magnate"},
    {"id":77114, "name": "Methamorphosis"},
    {"id":11942, "name": "Silver Magnate"},
    {"id":2078, "name": "Zephyr"},


    ### Mining
    ## Frigate Ore
    {"id": 32880, "name": "Venture"},
    {"id": 37135, "name": "Endurance"},
    {"id": 33697, "name": "Prospect"},

    # Mining Badge
    {"id":17476, "name": "Covetor"},
    {"id":17480, "name": "Procurer"},
    {"id":17478, "name": "Retriever"},

    # Exhumers
    {"id":22544, "name": "Hulk"},
    {"id":22548, "name": "Mackinaw"},
    {"id":22546, "name": "Skiff"},

    # ORE
    {"id":2998, "name": "Noctis"},
    {"id":28606, "name": "Orca"},
    {"id":42244, "name": "Porpoise"},


    ### Haulers
    # Haulers Amarr
    {"id":1944, "name": "Bestower"},
    {"id":19744, "name": "Sigil"},
    {"id":12753, "name": "Impel"},
    {"id":12733, "name": "Prorator"},

    # Haulers Caldari
    {"id":648, "name": "Badger"},
    {"id":649, "name": "Tayra"},
    {"id":12731, "name": "Bustard"},
    {"id":12729, "name": "Crane"},

    # Haulers Gallente
    {"id":655, "name": "Epithal"},
    {"id":657, "name": "Iteron Mark V"},
    {"id":654, "name": "Kryos"},
    {"id":656, "name": "Miasmos"},
    {"id":650, "name": "Nereus"},
    {"id":12745, "name": "Occator"},
    {"id":12743, "name": "Viator"},

    # Haulers Minmatar
    {"id":651, "name": "Hoarder"},
    {"id":652, "name": "Mammoth"},
    {"id":653, "name": "Wreathe"},
    {"id":12747, "name": "Mastodon"},
    {"id":12735, "name": "Prowler"},


    ## Destroyers
    # Destroyers Amarr
    {"id":16236, "name": "Coercer"},
    {"id":73789, "name": "Coercer Navy Issue"},
    {"id":32874, "name": "Dragoon"},
    {"id":37481, "name": "Pontifex"},
    {"id":22452, "name": "Heretic"},
    {"id":34317, "name": "Confessor"},

    # Destroyers Caldari
    {"id":32876, "name": "Corax"},
    {"id":16238, "name": "Cormorant"},
    {"id":73795, "name": "Cormorant Navy Issue"},
    {"id":37482, "name": "Stork"},
    {"id":22464, "name": "Flycatcher"},
    {"id":34828, "name": "Jackdaw"},

    # Destroyers Gallente
    {"id":32872, "name": "Algos"},
    {"id":16240, "name": "Catalyst"},
    {"id":73796, "name": "Catalyst Navy Issue"},
    {"id":37483, "name": "Magus"},
    {"id":22460, "name": "Eris"},
    {"id":35683, "name": "Hecate"},

    # Destroyers Minmatar
    {"id":32878, "name": "Talwar"},
    {"id":16242, "name": "Thrasher"},
    {"id":73794, "name": "Thrasher Fleet Issue"},
    {"id":37480, "name": "Bifrost"},
    {"id":22456, "name": "Sabre"},
    {"id":34562, "name": "Spivul"},

    # Destroyers Triglavian
    {"id":49710, "name": "Kikimora"},
    {"id":52254, "name": "Draugur"},

    # Destroyers Special Edition
    {"id":42685, "name": "Sunesis"},

    ##Cruisers
    # Cruisers Amarr
    {"id":628, "name": "Arbitrator"},
    {"id":625, "name": "Augoror"},
    {"id":624, "name": "Maller"},
    {"id":2006, "name": "Omen"},
    {"id":29337, "name": "Augoror Navy Issue"},
    {"id":17709, "name": "Omen Navy Issue"},
    {"id":12019, "name": "Sacrilege"},
    {"id":12003, "name": "Zealot"},
    {"id":12017, "name": "Devoter"},
    {"id":11987, "name": "Guardian"},
    {"id":20125, "name": "Curse"},
    {"id":11965, "name": "Pilgrim"},
    {"id":29986, "name": "Legion"},

    # Cruisers Caldari
    {"id":632, "name": "Blackbird"},
    {"id":621, "name": "Caracal"},
    {"id":623, "name": "Moa"},
    {"id":620, "name": "Osprey"},
    {"id":17634, "name": "Caracal Navy Issue"},
    {"id":29340, "name": "Osprey Navy Issue"},
    {"id":11993, "name": "Cerberus"},
    {"id":12011, "name": "Eagle"},
    {"id":11995, "name": "Onyx"},
    {"id":11985, "name": "Basilisk"},
    {"id":11957, "name": "Falcon"},
    {"id":11959, "name": "Rook"},
    {"id":29984, "name": "Tengu"},

    # Cruisers Gallente
    {"id":633, "name": "Celestis"},
    {"id":634, "name": "Exequror"},
    {"id":627, "name": "Thorax"},
    {"id":626, "name": "Vexor"},
    {"id":29344, "name": "Exequror Navy Issue"},
    {"id":17843, "name": "Vexor Navy Issue"},
    {"id":12023, "name": "Deimos"},
    {"id":12005, "name": "Ishtar"},
    {"id":12021, "name": "Phobos"},
    {"id":11989, "name": "Oneiros"},
    {"id":11969, "name": "Arazu"},
    {"id":11971, "name": "Lacesis"},
    {"id":29988, "name": "Proteus"},

    # Cruisers Minmatar
    {"id":630, "name": "Bellicose"},
    {"id":629, "name": "Rupture"},
    {"id":631, "name": "Scythe"},
    {"id":622, "name": "Stabber"},
    {"id":29336, "name": "Scythe Navy Issue"},
    {"id":17713, "name": "Stabber Navy Issue"},
    {"id":12015, "name": "Muninn"},
    {"id":11999, "name": "Vagabond"},
    {"id":12013, "name": "Broadsword"},
    {"id":11978, "name": "Scimitar"},
    {"id":11961, "name": "Huginn"},
    {"id":11963, "name": "Rapier"},
    {"id":29990, "name": "Loki"},

    # Cruisers EDENCOM
    {"id":54732, "name": "Stormbringer"},

    # Cruisers Triglavian
    {"id":52252, "name": "Ikitursa"},
    {"id":49713, "name": "Zarmazd"},
    {"id":49712, "name": "Rodiva"},
    {"id":47270, "name": "Vedmak"},

    # Cruisers Pirate
    {"id":17922, "name": "Ashimmu"},
    {"id":17720, "name": "Cynabal"},
    {"id":17715, "name": "Gila"},
    {"id":33818, "name": "Orthus"},
    {"id":17718, "name": "Phantasm"},
    {"id":33470, "name": "Stratios"},
    {"id":17722, "name": "Vigilant"},

    # Cruisers CONCORD
    {"id":45534, "name": "Monitor"},

    # Cruisers Special Edition
    {"id":34590, "name": "Victorieux Luxury Yacht"},


    ### BattleCruisers
    # BattleCruisers Amarr
    {"id":24696, "name": "Harbinger"},
    {"id":33155, "name": "Habinger Navy Issue"},
    {"id":4302, "name": "Oracle"},
    {"id":16233, "name": "Prophecy"},
    {"id":72872, "name": "Prophecy Navy Issue"},
    {"id":22448, "name": "Absolution"},
    {"id":22474, "name": "Damnation"},

    # BattleCruisers Caldari
    {"id":24698, "name": "Drake"},
    {"id":33153, "name": "Drake Navy Issue"},
    {"id":16227, "name": "Ferox"},
    {"id":72812, "name": "Ferox Navy Issue"},
    {"id":4306, "name": "Naga"},
    {"id":22470, "name": "Nighthawk"},
    {"id":22446, "name": "Vulture"},

    # BattleCruisers Gallente
    {"id":16229, "name": "Brutix"},
    {"id":33151, "name": "Brutix Navy Issue"},
    {"id":24700, "name": "Myrmidon"},
    {"id":72869, "name": "Myrmidon Navy Issue"},
    {"id":4308, "name": "Talos"},
    {"id":22466, "name": "Astarte"},
    {"id":22442, "name": "Eos"},

    # BattleCruisers Minmatar
    {"id":16231, "name": "Cyclone"},
    {"id":72811, "name": "Cyclone Navy Issue"},
    {"id":24702, "name": "Hurricane"},
    {"id":33157, "name": "Hurricane Navy Issue"},
    {"id":4310, "name": "Tornado"},
    {"id":22468, "name": "Claymore"},
    {"id":22444, "name": "Sleipnir"},

    # BattleCruisers Triglavian
    {"id":49711, "name": "Drekavac"},

    # BattleCruiser Special Edition
    {"id":3756, "name": "Gnosis"},


    ### BattleShips
    # BattleShips Amarr
    {"id":24692, "name": "Abaddon"},
    {"id":642, "name": "Apocalypse"},
    {"id":17726, "name": "Apocalypse Navy Issue"},
    {"id":643, "name": "Armageddon"},
    {"id":32305, "name": "Armageddon Navy Issue"},
    {"id":22428, "name": "Redeemer"},
    {"id":28659, "name": "Paladin"},

    # BattleShips Caldari
    {"id":638, "name": "Raven"},
    {"id":17636, "name": "Raven Navy Issue"},
    {"id":24688, "name": "Rokh"},
    {"id":640, "name": "Scorpion"},
    {"id":32309, "name": "Scorpion Navy Issue"},
    {"id":22436, "name": "Widow"},
    {"id":28710, "name": "Golem"},

    # BattleShips Gallente
    {"id":645, "name": "Dominix"},
    {"id":32307, "name": "Dominix Navy Issue"},
    {"id":24690, "name": "Hyperion"},
    {"id":641, "name": "Megathron"},
    {"id":17728, "name": "Megathron Navy Issue"},
    {"id":22430, "name": "Sin"},
    {"id":28661, "name": "Kronos"},

    # BattleShips Minmatar
    {"id":24694, "name": "Maelstrom"},
    {"id":639, "name": "Tempest"},
    {"id":17732, "name": "Tempest Fleet Issue"},
    {"id":644, "name": "Typhoon"},
    {"id":32311, "name": "Typhoon Fleet Issue"},
    {"id":22440, "name": "Panther"},
    {"id":28665, "name": "Vargur"},

    # BattleShips EDENCOM
    {"id":54733, "name": "Thunderchild"},

    # BattleShips Triglavian
    {"id":47271, "name": "Leshak"},

    # BattleShips Pirate
    {"id":33820, "name": "Barghest"},
    {"id":17920, "name": "Bhaalgorn"},
    {"id":17738, "name": "Machariel"},
    {"id":33472, "name": "Nestor"},
    {"id":17736, "name": "Nightmare"},
    {"id":17918, "name": "Rattlesnake"},
    {"id":17740, "name": "Vindicator"},

    # Special Edition Battleships
    {"id":47466, "name": "Praxis"},
    {"id":44996, "name": "Marshal"},


    ### Capital Ships
    # Capital Industrial Ships ORE
    {"id":28352, "name": "Rorqual"},
    {"id":34328, "name": "Bowhead"},

    ## Carriers Amarr
    {"id":23919, "name": "Aeon"},
    {"id":23757, "name": "Archon"},

    # Carriers Caldari
    {"id":23915, "name": "Chimera"},
    {"id":23917, "name": "Wyvern"},

    # Carriers Gallente
    {"id":23913, "name": "Nyx"},
    {"id":23911, "name": "Thanatos"},
    {"id":42132, "name": "Vanguard"},
    {"id":42125, "name": "Vendetta"},

    # Carriers Minmatar
    {"id":22852, "name": "Hel"},
    {"id":24483, "name": "Nidhoggur"},
    {"id":3514, "name": "Revenant"},

    ## Dreadnoughts
    # Dreadnoughts Amarr
    {"id":19720, "name": "Revelation"},
    {"id":73790, "name": "Revelation Navy Issue"},
    {"id":77283, "name": "Bane"},

    # Dreadnoughts Caldari
    {"id":19726, "name": "Phoenix"},
    {"id":73793, "name": "Phoenix Navy Issue"},
    {"id":77284, "name": "Karura"},

    # Dreadnoughts Gallente
    {"id":764, "name": "Moros"},
    {"id":73792, "name": "Moros Navy Issue"},
    {"id":77281, "name": "Hubris"},

    # Dreadnoughts Minmatar
    {"id":765, "name": "Naglfar"},
    {"id":73787, "name": "Naglfar Fleet Issue"},
    {"id":77288, "name": "Valravn"},

    # Dreadnoughts Pirate
    {"id":45647, "name": "Caiman"},
    {"id":42243, "name": "Chemosh"},
    {"id":42124, "name": "Vehement"},

    # Dreadnoughts Triglavian
    {"id":52907, "name": "Zirnitra"},

    ## Force Auxiliaries
    # Force Auxiliary Amarr
    {"id":37604, "name": "Apostle"},

    # Force Auxiliary Caldari
    {"id":37605, "name": "Minokawa"},
    {"id":45645, "name": "Loggerhead"},

    # Force Auxiliary Gallente
    {"id":37607, "name": "Ninazu"},
    {"id":42133, "name": "Venerable"},

    # Force Auxiliary Minmater
    {"id":37606, "name": "Lif"},
    {"id":42242, "name": "Dagon"},

    ## Freighters
    {"id":20183, "name": "Providence"},
    {"id":20185, "name": "Charon"},
    {"id":20187, "name": "Obelisk"},
    {"id":20189, "name": "Fenrir"},

    ## Jump Freightes
    {"id":28850, "name": "Ark"},
    {"id":28844, "name": "Rhea"},
    {"id":28848, "name": "Anshar"},
    {"id":28846, "name": "Nomad"},

    ### Titans
    {"id":11567, "name": "Avatar"},
    {"id":671, "name": "Erebus"},
    {"id":45649, "name": "Komodo"},
    {"id":3764, "name": "Leviathan"},
    {"id":42241, "name": "Molok"},
    {"id":23773, "name": "Ragnarok"},
    {"id":42126, "name": "Vanquisher"},


    ### Shield
    ## Shield Hardeners
    # Multispectrum Shield Hardeners
    {"id":578, "name": "Multispectum Shield Hardener I"},
    {"id":54291, "name": "Enduring Multispectum Shield Hardener"},
    {"id":9632, "name": "Compact Multispectum Shield Hardener"},
    {"id":2281, "name": "Multispectum Shield Hardener II"},
    {"id":17498, "name": "Caldari Navy Multispectum Shield Hardener"},
    {"id":13998, "name": "Domination Multispectum Shield Hardener I"},
    {"id":13969, "name": "Dread Guristas Multispectum Shield Hardener"},
    {"id":20637, "name": "'Posse' Multispectum Shield Hardener I"},
    {"id":4346, "name": "Gistum A-Type Multispectum Shield Hardener"},
    {"id":4345, "name": "Gistum B-Type Multispectum Shield Hardener"},
    {"id":2050, "name": "Gistum C-Type Multispectum Shield Hardener"},
    {"id":4347, "name": "Pithum A-Type Multispectum Shield Hardener"},
    {"id":4348, "name": "Pithum B-Type Multispectum Shield Hardener"},
    {"id":4349, "name": "Pithum C-Type Multispectum Shield Hardener"},
    {"id":14767, "name": "Estamel's Modified Multispectum Shield Hardener"},
    {"id":14764, "name": "Kaikka's Modified Multispectum Shield Hardener"},
    {"id":14765, "name": "Thon's Modified Multispectum Shield Hardener"},
    {"id":14766, "name": "Vepas' Modified Multispectum Shield Hardener"},

    # EM Shield Hardeners
    {"id":2293, "name": "EM Shield Hardener"},
    {"id":30420, "name": "Civilian EM Shield Hardener"},
    {"id":54292, "name": "Enduring EM Shield Hardener"},
    {"id":9622, "name": "Compact EM Shield Hardener"},
    {"id":2301, "name": "EM Shield Hardener II"},
    {"id":20639, "name": "'Poacher' EM Shield Hardener"},
    {"id":17499, "name": "Caldari Navy EM Shield Hardener"},
    {"id":13994, "name": "Domination EM Shield Hardener"},
    {"id":13965, "name": "Dread Guristas EM Shield Hardener"},
    {"id":19279, "name": "Gist A-Type EM Shield Hardener"},
    {"id":19265, "name": "Gist B-Type EM Shield Hardener"},
    {"id":19263, "name": "Gist C-Type EM Shield Hardener"},
    {"id":19281, "name": "Gist X-Type EM Shield Hardener"},
    {"id":19280, "name": "Pith A-Type EM Shield Hardener"},
    {"id":19266, "name": "Pith B-Type EM Shield Hardener"},
    {"id":19264, "name": "Pith C-Type EM Shield Hardener"},
    {"id":19282, "name": "Pith X-Type EM Shield Hardener"},
    {"id":14755, "name": "Estamel's Modified EM Shield Hardener"},
    {"id":14752, "name": "Kaikka's Modified EM Shield Hardener"},
    {"id":14753, "name": "Thon's Modified EM Shield Hardener"},
    {"id":14754, "name": "Vepas' Modified EM Shield Hardener"},

    # Explosive Shield Hardeners
    {"id": 2289, "name": "Explosive Shield Hardener"},
    {"id": 30422, "name": "Civilian Explosive Shield Hardener"},
    {"id": 54293, "name": "Enduring Explosive Shield Hardener"},
    {"id": 9646, "name": "Compact Explosive Shield Hardener"},
    {"id": 2297, "name": "Explosive Shield Hardener II"},
    {"id": 20641, "name": "'Snake Eyes' Explosive Shield Hardener"},
    {"id": 17496, "name": "Caldari Navy Explosive Shield Hardener"},
    {"id": 13996, "name": "Domination Explosive Shield Hardener"},
    {"id": 13967, "name": "Dread Guristas Explosive Shield Hardener"},
    {"id": 19275, "name": "Gist A-Type Explosive Shield Hardener"},
    {"id": 19269, "name": "Gist B-Type Explosive Shield Hardener"},
    {"id": 19259, "name": "Gist C-Type Explosive Shield Hardener"},
    {"id": 19285, "name": "Gist X-Type Explosive Shield Hardener"},
    {"id": 19276, "name": "Pith A-Type Explosive Shield Hardener"},
    {"id": 19270, "name": "Pith B-Type Explosive Shield Hardener"},
    {"id": 19260, "name": "Pith C-Type Explosive Shield Hardener"},
    {"id": 19286, "name": "Pith X-Type Explosive Shield Hardener"},
    {"id": 14759, "name": "Estamel's Modified Explosive Shield Hardener"},
    {"id": 14756, "name": "Kaikka's Modified Explosive Shield Hardener"},
    {"id": 14757, "name": "Thon's Modified Explosive Shield Hardener"},
    {"id": 14758, "name": "Vepas' Modified Explosive Shield Hardener"},

    # Kinetic Shield Hardeners
    {"id": 2291, "name": "Kinetic Shield Hardener"},
    {"id": 30424, "name": "Civilian Kinetic Shield Hardener"},
    {"id": 54294, "name": "Enduring Kinetic Shield Hardener"},
    {"id": 9608, "name": "Compact Kinetic Shield Hardener"},
    {"id": 2299, "name": "Kinetic Shield Hardener II"},
    {"id": 20633, "name": "'Nugget' Kinetic Shield Hardener"},
    {"id": 17495, "name": "Caldari Navy Kinetic Shield Hardener"},
    {"id": 13997, "name": "Domination Kinetic Shield Hardener"},
    {"id": 13968, "name": "Dread Guristas Kinetic Shield Hardener"},
    {"id": 19273, "name": "Gist A-Type Kinetic Shield Hardener"},
    {"id": 19271, "name": "Gist B-Type Kinetic Shield Hardener"},
    {"id": 19257, "name": "Gist C-Type Kinetic Shield Hardener"},
    {"id": 19287, "name": "Gist X-Type Kinetic Shield Hardener"},
    {"id": 19274, "name": "Pith A-Type Kinetic Shield Hardener"},
    {"id": 19272, "name": "Pith B-Type Kinetic Shield Hardener"},
    {"id": 19258, "name": "Pith C-Type Kinetic Shield Hardener"},
    {"id": 19288, "name": "Pith X-Type Kinetic Shield Hardener"},
    {"id": 14751, "name": "Estamel's Modified Kinetic Shield Hardener"},
    {"id": 14748, "name": "Kaikka's Modified Kinetic Shield Hardener"},
    {"id": 14749, "name": "Thon's Modified Kinetic Shield Hardener"},
    {"id": 14750, "name": "Vepas' Modified Kinetic Shield Hardener"},

    # Thermal Shield Hardeners
    {"id": 2295, "name": "Thermal Shield Hardener"},
    {"id": 30342, "name": "Civilian Thermal Shield Hardener"},
    {"id": 54295, "name": "Enduring Thermal Shield Hardener"},
    {"id": 9660, "name": "Compact Thermal Shield Hardener"},
    {"id": 2303, "name": "Thermal Shield Hardener II"},
    {"id": 20635, "name": "'Desert Heat' Thermal Shield Hardener"},
    {"id": 17497, "name": "Caldari Navy Thermal Shield Hardener"},
    {"id": 13995, "name": "Domination Thermal Shield Hardener"},
    {"id": 13966, "name": "Dread Guristas Thermal Shield Hardener"},
    {"id": 19277, "name": "Gist A-Type Thermal Shield Hardener"},
    {"id": 19267, "name": "Gist B-Type Thermal Shield Hardener"},
    {"id": 19261, "name": "Gist C-Type Thermal Shield Hardener"},
    {"id": 19283, "name": "Gist X-Type Thermal Shield Hardener"},
    {"id": 19278, "name": "Pith A-Type Thermal Shield Hardener"},
    {"id": 19268, "name": "Pith B-Type Thermal Shield Hardener"},
    {"id": 19262, "name": "Pith C-Type Thermal Shield Hardener"},
    {"id": 19284, "name": "Pith X-Type Thermal Shield Hardener"},
    {"id": 14763, "name": "Estamel's Modified Thermal Shield Hardener"},
    {"id": 14760, "name": "Kaikka's Modified Thermal Shield Hardener"},
    {"id": 14761, "name": "Thon's Modified Thermal Shield Hardener"},
    {"id": 14762, "name": "Vepas' Modified Thermal Shield Hardener"},

    # Scriptable Shield Hardeners
    {"id":41516 , "name": "Capital Flex Shield Hardener I"},
    {"id":41528, "name": "Capital Flex Shield Hardener II"},
    {"id":41531, "name": "Domination Capital Flex Shield Hardener"},
    {"id":41530, "name": "Dread Guristas Capital Flex Shield Hardener"},
    {"id":41529 , "name": "True Sansha Capital Flex Shield Hardener"},

    # Shield Flux Coils
    {"id":1254, "name": "Shield Flux Coil I"},
    {"id":8297, "name": "Mark I Compact Shield Flux Coil"},
    {"id":8295, "name": "Type-D Restained Shield Flux Coil"},
    {"id":1256, "name": "Shield Flux Coil II"},
    {"id":508, "name": "'Basic' Shield Flux Coil"},
    {"id":37825, "name": "Dread Guristas Shield Flux Coil"},

    # Shield Power Relays
    {"id":2331, "name": "Shield Power Relay"},
    {"id":8337, "name": "Mark I Compact Shield Power Relay"},
    {"id":8335, "name": "Type-D Restrained Shield Power Relay"},
    {"id":1422, "name": "Shield Power Relay II"},
    {"id":1419, "name": "'Basic' Shield Power Relay"},
    {"id":37820, "name": "Caldari Navy Shield Power Relay"},

    # Shield Rechargers
    {"id":393, "name": "Shield Recharger I"},
    {"id":6485, "name": "M51 Benefactor Compact Shield Recharger"},
    {"id":394, "name": "Shield Recharger II"},
    {"id":37805, "name": "Republic Fleet Shield Recharger"},

    # Shield Resistance Amplifiers
    # EM Shield Amplifier
    {"id":1808, "name": "EM Shield Amplifier I"},
    {"id":9580, "name": "Compact EM Shield Amplifier"},
    {"id":2553, "name": "EM Shield Amplifier II"},
    {"id":1798, "name": "'Basic' EM Shield Amplifier"},
    {"id":20611, "name": "'Prospector' EM Shield Amplifier"},
    {"id":15909, "name": "Caldari Navy EM Shield Amplifier"},
    {"id":15917, "name": "Republic Fleet EM Shield Amplifier"},
    {"id":14041, "name": "Domination EM Shield Amplifier"},
    {"id":14043, "name": "Dread Guristas EM Shield Amplifier"},
    {"id":19255, "name": "Gistum A-Type EM Shield Amplifier"},
    {"id":19247, "name": "Gistum B-Type EM Shield Amplifier"},
    {"id":19245, "name": "Gistum C-Type EM Shield Amplifier"},
    {"id":19231, "name": "Pithum A-Type EM Shield Amplifier"},
    {"id":19233, "name": "Pithum B-Type EM Shield Amplifier"},
    {"id":19215, "name": "Pithum C-Type EM Shield Amplifier"},
    {"id":14746, "name": "Estamel's Modified EM Shield Amplifier"},
    {"id":14630, "name": "Hakim's Modified EM Shield Amplifier"},
    {"id":14740, "name": "Kaikka's Modified EM Shield Amplifier"},
    {"id":14742, "name": "Thon's Modified EM Shield Amplifier"},
    {"id":14634, "name": "Tobias' Modified EM Shield Amplifier"},
    {"id":14744, "name": "Vepas' Modified EM Shield Amplifier"},

    # Explosive Shield Amplifier
    {"id": 2529, "name": "Explosive Shield Amplifier I"},
    {"id": 9556, "name": "Compact Explosive Shield Amplifier"},
    {"id": 2531, "name": "Explosive Shield Amplifier II"},
    {"id": 1804, "name": "'Basic' Explosive Shield Amplifier"},
    {"id": 20605, "name": "'Whiskey' Explosive Shield Amplifier"},
    {"id": 15915, "name": "Caldari Navy Explosive Shield Amplifier"},
    {"id": 15923, "name": "Republic Fleet Explosive Shield Amplifier"},
    {"id": 14029, "name": "Domination Explosive Shield Amplifier"},
    {"id": 14031, "name": "Dread Guristas Explosive Shield Amplifier"},
    {"id": 19249, "name": "Gistum A-Type Explosive Shield Amplifier"},
    {"id": 19235, "name": "Gistum B-Type Explosive Shield Amplifier"},
    {"id": 19233, "name": "Gistum C-Type Explosive Shield Amplifier"},
    {"id": 19225, "name": "Pithum A-Type Explosive Shield Amplifier"},
    {"id": 19217, "name": "Pithum B-Type Explosive Shield Amplifier"},
    {"id": 19209, "name": "Pithum C-Type Explosive Shield Amplifier"},
    {"id": 14722, "name": "Estamel's Modified Explosive Shield Amplifier"},
    {"id": 14606, "name": "Hakim's Modified Explosive Shield Amplifier"},
    {"id": 14716, "name": "Kaikka's Modified Explosive Shield Amplifier"},
    {"id": 14718, "name": "Thon's Modified Explosive Shield Amplifier"},
    {"id": 14610, "name": "Tobias' Modified Explosive Shield Amplifier"},
    {"id": 14720, "name": "Vepas' Modified Explosive Shield Amplifier"},

    # Kinetic Shield Amplifier
    {"id": 2545, "name": "Kinetic Shield Amplifier I"},
    {"id": 9582, "name": "Compact Kinetic Shield Amplifier"},
    {"id": 2547, "name": "Kinetic Shield Amplifier II"},
    {"id": 1802, "name": "'Basic' Kinetic Shield Amplifier"},
    {"id": 20609, "name": "'Cactus' Kinetic Shield Amplifier"},
    {"id": 15911, "name": "Caldari Navy Kinetic Shield Amplifier"},
    {"id": 15919, "name": "Republic Fleet Kinetic Shield Amplifier"},
    {"id": 14037, "name": "Domination Kinetic Shield Amplifier"},
    {"id": 14039, "name": "Dread Guristas Kinetic Shield Amplifier"},
    {"id": 19253, "name": "Gistum A-Type Kinetic Shield Amplifier"},
    {"id": 19243, "name": "Gistum B-Type Kinetic Shield Amplifier"},
    {"id": 19241, "name": "Gistum C-Type Kinetic Shield Amplifier"},
    {"id": 19229, "name": "Pithum A-Type Kinetic Shield Amplifier"},
    {"id": 19221, "name": "Pithum B-Type Kinetic Shield Amplifier"},
    {"id": 19213, "name": "Pithum C-Type Kinetic Shield Amplifier"},
    {"id": 14738, "name": "Estamel's Modified Kinetic Shield Amplifier"},
    {"id": 14622, "name": "Hakim's Modified Kinetic Shield Amplifier"},
    {"id": 14732, "name": "Kaikka's Modified Kinetic Shield Amplifier"},
    {"id": 14734, "name": "Thon's Modified Kinetic Shield Amplifier"},
    {"id": 14626, "name": "Tobias' Modified Kinetic Shield Amplifier"},
    {"id": 14736, "name": "Vepas' Modified Kinetic Shield Amplifier"},

    # Thermal Shield Amplifier
    {"id": 2537, "name": "Thermal Shield Amplifier I"},
    {"id": 9568, "name": "Compact Thermal Shield Amplifier"},
    {"id": 2539, "name": "Thermal Shield Amplifier II"},
    {"id": 1800, "name": "'Basic' Thermal Shield Amplifier"},
    {"id": 20608, "name": "'High Noon' Thermal Shield Amplifier"},
    {"id": 15913, "name": "Caldari Navy Thermal Shield Amplifier"},
    {"id": 15921, "name": "Republic Fleet Thermal Shield Amplifier"},
    {"id": 14033, "name": "Domination Thermal Shield Amplifier"},
    {"id": 14035, "name": "Dread Guristas Thermal Shield Amplifier"},
    {"id": 19251, "name": "Gistum A-Type Thermal Shield Amplifier"},
    {"id": 19239, "name": "Gistum B-Type Thermal Shield Amplifier"},
    {"id": 19237, "name": "Gistum C-Type Thermal Shield Amplifier"},
    {"id": 19227, "name": "Pithum A-Type Thermal Shield Amplifier"},
    {"id": 19219, "name": "Pithum B-Type Thermal Shield Amplifier"},
    {"id": 19211, "name": "Pithum C-Type Thermal Shield Amplifier"},
    {"id": 14730, "name": "Estamel's Modified Thermal Shield Amplifier"},
    {"id": 14614, "name": "Hakim's Modified Thermal Shield Amplifier"},
    {"id": 14724, "name": "Kaikka's Modified Thermal Shield Amplifier"},
    {"id": 14726, "name": "Thon's Modified Thermal Shield Amplifier"},
    {"id": 14618, "name": "Tobias' Modified Thermal Shield Amplifier"},
    {"id": 14728, "name": "Vepas' Modified Thermal Shield Amplifier"},


    ### Remote Shield Booster
    # Micro Shield Boosters
    {"id":406, "name": "Micro Remote Shield Booster II"},

    # Small Shield Boosters
    {"id":41480, "name": "Small Ancillary Remote Shield Booster"},
    {"id":8535, "name": "Small Asymmetric Enduring Remote Shield Booster"},
    {"id":8531, "name": "Small Murky Compact Remote Shield Booster"},
    {"id":3586, "name": "Small Remote Shield Booster I"},
    {"id":3588, "name": "Small Remote Shield Booster II"},
    {"id":8537, "name": "Small S95a Scoped Remote Shield Booster"},
    {"id":405, "name": "'Micro' Remote Shield Booster"},
    {"id":19133, "name": "Gistii A-Type Small Remote Shield Booster"},
    {"id":19131, "name": "Gistii B-Type Small Remote Shield Booster"},
    {"id":19129, "name": "Gistii C-Type Small Remote Shield Booster"},
    {"id":19139, "name": "Pithi A-Type Small Remote Shield Booster"},
    {"id":19137, "name": "Pithi B-Type Small Remote Shield Booster"},
    {"id":19135, "name": "Pithi C-Type Small Remote Shield Booster"},

    # Medium Shield Boosters
    {"id": 41481, "name": "Medium Ancillary Remote Shield Booster"},
    {"id": 8583, "name": "Medium Asymmetric Enduring Remote Shield Booster"},
    {"id": 8579, "name": "Medium Murky Compact Remote Shield Booster"},
    {"id": 3596, "name": "Medium Remote Shield Booster I"},
    {"id": 3598, "name": "Medium Remote Shield Booster II"},
    {"id": 8585, "name": "Medium S95a Scoped Remote Shield Booster"},
    {"id": 19145, "name": "Gistii A-Type Medium Remote Shield Booster"},
    {"id": 19143, "name": "Gistii B-Type Medium Remote Shield Booster"},
    {"id": 19141, "name": "Gistii C-Type Medium Remote Shield Booster"},
    {"id": 19151, "name": "Pithi A-Type Medium Remote Shield Booster"},
    {"id": 19149, "name": "Pithi B-Type Medium Remote Shield Booster"},
    {"id": 19147, "name": "Pithi C-Type Medium Remote Shield Booster"},

    # Large Shield Boosters
    {"id": 41482, "name": "Large Ancillary Remote Shield Booster"},
    {"id": 8639, "name": "Large Asymmetric Enduring Remote Shield Booster"},
    {"id": 8635, "name": "Large Murky Compact Remote Shield Booster"},
    {"id": 3606, "name": "Large Remote Shield Booster I"},
    {"id": 3608, "name": "Large Remote Shield Booster II"},
    {"id": 8641, "name": "Large S95a Scoped Remote Shield Booster"},

    # Capital Shield Boosters
    {"id": 41483, "name": "Capital Ancillary Remote Shield Booster"},
    {"id": 41469, "name": "Capital Asymmetric Enduring Remote Shield Booster"},
    {"id": 41470, "name": "Capital Murky Compact Remote Shield Booster"},
    {"id": 3616, "name": "Capital Remote Shield Booster I"},
    {"id": 3618, "name": "Capital Remote Shield Booster II"},
    {"id": 41471, "name": "Capital S95a Scoped Remote Shield Booster"},
    {"id": 3544, "name": "CONCORD Capital Remote Shield Booster"},
    {"id": 41474, "name": "Domination Capital Remote Shield Booster"},
    {"id": 41473, "name": "Dread Guristas Capital Remote Shield Booster"},
    {"id": 41472, "name": "True Sansha Capital Remote Shield Booster"},
]

items = items_eve


#     {"id": , "name": ""},

#    {"id": 34, "name": "Tritanium"},
#    {"id": 35, "name": "Pyerite"},
#    {"id": 3756, "name": "Gnosis"}


# Генератор id
#items = [{'id': id, 'name': id} for id in range(1, 80001)]
#id = {'id':[]}


print(f'Items: {len(items)}')

regions = [
#    {"id": 10000002, "name": "The Forge"},
    {"id": 10000043, "name": "Domain"}
]

stations = [
#   {"id": 60003760, "name": "Jita 4-4 - Caldari Navy Assembly Plant"},
    {"id": 60008494, "name": "Amarr VIII (Oris) - Emperor Family Academy"}
]

sales_tax = 0.05  # Здесь нужно указать комиссию на продажу (например, 0.05 для 5%)

for item in items:
    item_id = item["id"]
    item_name = item["name"]

    for region in regions:
        region_id = region["id"]
        region_name = region["name"]

        for station in stations:
            station_id = station["id"]
            station_name = station["name"]

            item_prices = get_item_prices(item_id, item_name, region_id, region_name, station_id, station_name, sales_tax)

            if item_prices and station_id in item_prices:
#                print(f"\nТовар: '{item_name}' в регионе '{region_name}' на станции '{station_name}':")
                for station_id, station_prices in item_prices.items():
                    if station_prices and station_prices["profit_sell_percentage"] <= 0.1:
                        print(f"\nТовар: '{item_name}' в регионе '{region_name}' на станции '{station_name}':")

                        min_sell_price = station_prices["min_sell_price"]
                        max_buy_price = station_prices["max_buy_price"]
                        trade_volume = station_prices["trade_volume"]
                        profit_sell = station_prices["profit_sell"]
                        profit_sell_percentage = station_prices["profit_sell_percentage"]

                        print(f"Sell Price: {min_sell_price:,.0f}, Buy Price: {max_buy_price:,.0f}")
                        print(f"Торговый объем - {trade_volume:,.0f} items")
                        print(f"Profit: {profit_sell:,.2f} isk - {profit_sell_percentage:.2f}%")
###                        print(f"Процент прибыли от продажи - {profit_sell_percentage:.2f}%")
##                    if station_prices:
##                        id["id"].append(item_name)
                    else:
                        pass
#                        print(f"Цены недоступны для станции '{station_name}'")
##                        print('.', end="")
            else:
                pass
#                print(f"Не удалось получить цены на товар '{item_name}' в регионе '{region_name}' на станции '{station_name}'")

#print(id)
print(f'\nTime: {time.time() - start_time} sec')

