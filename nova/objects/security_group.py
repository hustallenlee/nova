#    Copyright 2013 IBM Corp.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from oslo_utils import versionutils

from nova import db
from nova import objects
from nova.objects import base
from nova.objects import fields


@base.NovaObjectRegistry.register
class SecurityGroup(base.NovaPersistentObject, base.NovaObject):
    # Version 1.0: Initial version
    # Version 1.1: String attributes updated to support unicode
    # Version 1.2: Added uuid field for Neutron security groups.
    VERSION = '1.2'

    fields = {
        'id': fields.IntegerField(),
        'name': fields.StringField(),
        'description': fields.StringField(),
        'user_id': fields.StringField(),
        'project_id': fields.StringField(),
        # The uuid field is only used for Neutron security groups and is not
        # persisted to the Nova database.
        'uuid': fields.UUIDField()
        }

    def obj_make_compatible(self, primitive, target_version):
        target_version = versionutils.convert_version_to_tuple(target_version)
        if target_version < (1, 2) and 'uuid' in primitive:
            del primitive['uuid']

    @staticmethod
    def _from_db_object(context, secgroup, db_secgroup):
        for field in secgroup.fields:
            if field is not 'uuid':
                setattr(secgroup, field, db_secgroup[field])
        secgroup._context = context
        secgroup.obj_reset_changes()
        return secgroup

    @base.remotable_classmethod
    def get(cls, context, secgroup_id):
        db_secgroup = db.security_group_get(context, secgroup_id)
        return cls._from_db_object(context, cls(), db_secgroup)

    @base.remotable_classmethod
    def get_by_name(cls, context, project_id, group_name):
        db_secgroup = db.security_group_get_by_name(context,
                                                    project_id,
                                                    group_name)
        return cls._from_db_object(context, cls(), db_secgroup)

    @base.remotable
    def in_use(self):
        return db.security_group_in_use(self._context, self.id)

    @base.remotable
    def save(self):
        updates = self.obj_get_changes()
        # We don't store uuid in the Nova database so remove it if someone
        # mistakenly tried to save a neutron security group object. We only
        # need the uuid in the object for obj_to_primitive() calls where this
        # object is serialized and stored in the RequestSpec object.
        updates.pop('uuid', None)
        if updates:
            db_secgroup = db.security_group_update(self._context, self.id,
                                                   updates)
            self._from_db_object(self._context, self, db_secgroup)
        self.obj_reset_changes()

    @base.remotable
    def refresh(self):
        self._from_db_object(self._context, self,
                             db.security_group_get(self._context, self.id))


@base.NovaObjectRegistry.register
class SecurityGroupList(base.ObjectListBase, base.NovaObject):
    # Version 1.0: Initial version
    #              SecurityGroup <= version 1.1
    VERSION = '1.0'

    fields = {
        'objects': fields.ListOfObjectsField('SecurityGroup'),
        }

    def __init__(self, *args, **kwargs):
        super(SecurityGroupList, self).__init__(*args, **kwargs)
        self.objects = []
        self.obj_reset_changes()

    @base.remotable_classmethod
    def get_all(cls, context):
        groups = db.security_group_get_all(context)
        return base.obj_make_list(context, cls(context),
                                  objects.SecurityGroup, groups)

    @base.remotable_classmethod
    def get_by_project(cls, context, project_id):
        groups = db.security_group_get_by_project(context, project_id)
        return base.obj_make_list(context, cls(context),
                                  objects.SecurityGroup, groups)

    @base.remotable_classmethod
    def get_by_instance(cls, context, instance):
        groups = db.security_group_get_by_instance(context, instance.uuid)
        return base.obj_make_list(context, cls(context),
                                  objects.SecurityGroup, groups)


def make_secgroup_list(security_groups):
    """A helper to make security group objects from a list of names.

    Note that this does not make them save-able or have the rest of the
    attributes they would normally have, but provides a quick way to fill,
    for example, an instance object during create.
    """
    secgroups = objects.SecurityGroupList()
    secgroups.objects = []
    for name in security_groups:
        secgroup = objects.SecurityGroup()
        secgroup.name = name
        secgroups.objects.append(secgroup)
    return secgroups
