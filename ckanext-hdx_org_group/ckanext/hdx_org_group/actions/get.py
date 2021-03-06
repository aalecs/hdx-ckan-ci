'''
Created on April 24, 2015

@author: alexandru-m-g
'''

import pylons.config as config

import ckan.logic as logic
import ckan.model as model
import ckan.common as common
import ckan.lib.dictization as d

import ckanext.hdx_crisis.dao.country_data_access as country_data_access
import ckanext.hdx_org_group.dao.indicator_access as indicator_access
import ckanext.hdx_org_group.controllers.country_controller as ctrlr

json = common.json
get_action = logic.get_action
_get_or_bust = logic.get_or_bust
NotFound = logic.NotFound

IndicatorAccess = indicator_access.IndicatorAccess
dataseries_list = ctrlr.indicators_4_top_line_list


@logic.side_effect_free
def hdx_datasets_for_group(context, data_dict):
    '''
    Returns a paginated list of datasets for a group with 25 items per page.
    Options for sorting are: metadata_modified desc, title_case_insensitive desc, title_case_insensitive asc,
    views_recent desc, score desc ( only useful if query string is specified, should be combined
    with metadata_modified desc )
    :param id: the id of the group for which datasets are requested
    :type id: string
    :param page: page number starting from 1
    :type page: int
    :param sort: the field by which the datasets should be sorted. Defaults to 'metadata_modified desc'
    :type sort: string
    :param q: query string
    :type q: string
    :param type: 'all', 'indicators', 'datasets'. Defaults to 'all'
    :type q: string
    :return:
    '''

    skipped_keys = ['q', 'id', 'sort', 'type', 'page']

    id = _get_or_bust(data_dict, "id")

    limit = 25

    sort_option = data_dict.get('sort', 'metadata_modified desc')

    page = int(data_dict.get('page', 1))
    new_data_dict = {'sort': sort_option,
                 'rows': limit,
                 'start': (page-1) * limit,
                 }
    type = data_dict.get('type', None)
    if type == 'indicators':
        new_data_dict['ext_indicator'] = u'1'
    elif type == 'datasets':
        new_data_dict['ext_indicator'] = u'0'

    search_param_list = [
        key + ":" + value for key, value in data_dict.iteritems() if key not in skipped_keys]
    search_param_list.append(u'groups:{}'.format(id))

    if search_param_list != None:
        new_data_dict['fq'] = " ".join(
            search_param_list) + ' +dataset_type:dataset'

    if data_dict.get('q', None):
        new_data_dict['q'] = data_dict['q']

    query = get_action("package_search")(context, new_data_dict)

    return query


@logic.side_effect_free
def hdx_topline_num_for_group(context, data_dict):
    '''
    :param id: the id of the group for which top line numbers are requested
    :type id: string
    :return: a dict of top line numbers. Please note that depending on the selected group the source
    of the data ( either the datastore or CPS/indicators ) might be different. The data will have some fields
     that are specific to the source.
    '''
    id = _get_or_bust(data_dict, "id")
    group_info, custom_dict = get_group(id)

    datastore_id = custom_dict.get('topline_resource', None)

    if group_info.get('custom_loc', False) and datastore_id:
        #source is datastore
        crisis_data_access = country_data_access.ColombiaCrisisDataAccess(datastore_id)
        crisis_data_access.fetch_data(context)
        top_line_items = crisis_data_access.get_top_line_items()
        for item in top_line_items:
            item['source_system'] = 'datastore'
            del item['units']
    else:
        # source is CPS
        ckan_site_url = config.get('ckan.site_url')
        indicator_dao = IndicatorAccess(id, dataseries_list, {'periodType': 'LATEST_YEAR_BY_COUNTRY'})
        cps_top_line_items = indicator_dao.fetch_indicator_data_from_cps()
        ckan_data = indicator_dao.fetch_indicator_data_from_ckan()
        top_line_items = []
        for item in cps_top_line_items.get('results', {}):
            code = item.get('indicatorTypeCode', '')
            new_item = {
                'source_system': 'cps',
                'code': code,
                'title': item.get('indicatorTypeName', ''),
                'source_link': ckan_site_url + ckan_data.get(code, {}).get('datasetLink', ''),
                'source': item.get('sourceName', ''),
                'value': item.get('value', ''),
                'latest_date': item.get('time', ''),
                'units': item.get('unitName', )
            }
            top_line_items.append(new_item)

    return top_line_items


@logic.side_effect_free
def hdx_light_group_show(context, data_dict):
    '''
    Return a lightweight ( less resource intensive,faster but without datasets ) version of the group details
    :param id: the id of the group for which top line numbers are requested
    :type id: string
    '''

    id = _get_or_bust(data_dict, "id")
    group_dict = {}
    group = model.Group.get(id)
    if not group:
        raise NotFound
    #group_dict['group'] = group
    group_dict['id'] = group.id
    group_dict['name'] = group.name
    group_dict['image_url'] = group.image_url
    group_dict['display_name'] = group_dict['title'] = group.title
    group_dict['description'] = group.description
    group_dict['revision_id'] = group.revision_id

    result_list = []
    for name, extra in group._extras.iteritems():
        dictized = d.table_dictize(extra, context)
        if not extra.state == 'active':
            continue
        value = dictized["value"]
        result_list.append(dictized)

        #Keeping the above for backwards compatibility
        group_dict[name]= dictized["value"]

    group_dict['extras'] = sorted(result_list, key=lambda x: x["key"])
    return group_dict


def get_group(id):
    context = {'model': model, 'session': model.Session,
               'include_datasets': False,
               'for_view': True}
    data_dict = {'id': id}

    group_info = get_action('hdx_light_group_show')(context, data_dict)

    extras_dict = {item['key']: item['value'] for item in group_info.get('extras', {})}
    json_string = extras_dict.get('customization', None)
    if json_string:
        custom_dict = json.loads(json_string)
    else:
        custom_dict = {}

    return group_info, custom_dict