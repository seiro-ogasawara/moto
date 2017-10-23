from __future__ import unicode_literals
import time
import boto3
import string
import random
import hashlib
from moto.core import BaseBackend, BaseModel
from collections import OrderedDict
from .exceptions import (
    ResourceNotFoundException,
    InvalidRequestException
)


class FakeThing(BaseModel):
    def __init__(self, thing_name, thing_type, attributes, region_name):
        self.region_name = region_name
        self.thing_name = thing_name
        self.thing_type = thing_type
        self.attributes = attributes
        self.arn = 'arn:aws:iot:%s:1:thing/%s' % (self.region_name, thing_name)
        self.version = 1
        # TODO: we need to handle 'version'?

        # for iot-data
        self.thing_shadow = None

    def to_dict(self, include_default_client_id=False):
        obj = {
            'thingName': self.thing_name,
            'thingTypeName': self.thing_type.thing_type_name,
            'attributes': self.attributes,
            'version': self.version
        }
        if include_default_client_id:
            obj['defaultClientId'] = self.thing_name
        return obj


class FakeThingType(BaseModel):
    def __init__(self, thing_type_name, thing_type_properties, region_name):
        self.region_name = region_name
        self.thing_type_name = thing_type_name
        self.thing_type_properties = thing_type_properties
        t = time.time()
        self.metadata = {
            'deprecated': False,
            'creationData': int(t * 1000) / 1000.0
        }
        self.arn = 'arn:aws:iot:%s:1:thingtype/%s' % (self.region_name, thing_type_name)

    def to_dict(self):
        return {
            'thingTypeName': self.thing_type_name,
            'thingTypeProperties': self.thing_type_properties,
            'thingTypeMetadata': self.metadata
        }


class FakeCertificate(BaseModel):
    def __init__(self, certificate_pem, status, region_name):
        m = hashlib.sha256()
        m.update(certificate_pem)
        self.certificate_id = m.hexdigest()
        self.arn = 'arn:aws:iot:%s:1:cert/%s' % (region_name, self.certificate_id)
        self.certificate_pem = certificate_pem
        self.status = status

        # TODO: must adjust
        self.owner = '1'
        self.transfer_data = {}
        self.creation_date = time.time()
        self.last_modified_date = self.creation_date
        self.ca_certificate_id = None

    def to_dict(self):
        return {
            'certificateArn': self.arn,
            'certificateId': self.certificate_id,
            'status': self.status,
            'creationDate': self.creation_date
        }

    def to_description_dict(self):
        """
        You might need keys below in some situation
          - caCertificateId
          - previousOwnedBy
        """
        return {
            'certificateArn': self.arn,
            'certificateId': self.certificate_id,
            'status': self.status,
            'certificatePem': self.certificate_pem,
            'ownedBy': self.owner,
            'creationDate': self.creation_date,
            'lastModifiedDate': self.last_modified_date,
            'transferData': self.transfer_data
        }


class FakePolicy(BaseModel):
    def __init__(self, name, document, region_name):
        self.name = name
        self.document = document
        self.arn = 'arn:aws:iot:%s:1:policy/%s' % (region_name, name)
        self.version = '1' # TODO: handle version

    def to_get_dict(self):
        return {
            'policyName': self.name,
            'policyArn': self.arn,
            'policyDocument': self.document,
            'defaultVersionId': self.version
        }

    def to_dict_at_creation(self):
        return {
            'policyName': self.name,
            'policyArn': self.arn,
            'policyDocument': self.document,
            'policyVersionId': self.version
        }

    def to_dict(self):
        return {
            'policyName': self.name,
            'policyArn': self.arn,
        }

class IoTBackend(BaseBackend):
    def __init__(self, region_name=None):
        super(IoTBackend, self).__init__()
        self.region_name = region_name
        self.things = OrderedDict()
        self.thing_types = OrderedDict()
        self.certificates = OrderedDict()
        self.policies = OrderedDict()
        self.principal_policies = OrderedDict()
        self.principal_things = OrderedDict()

    def reset(self):
        region_name = self.region_name
        self.__dict__ = {}
        self.__init__(region_name)

    def create_thing(self, thing_name, thing_type_name, attribute_payload):
        thing_types = self.list_thing_types()
        thing_type = None
        if thing_type_name:
            filtered_thing_types = [_ for _ in thing_types if _.thing_type_name == thing_type_name]
            if len(filtered_thing_types) == 0:
                raise ResourceNotFoundException()
            thing_type = filtered_thing_types[0]
        if attribute_payload is None:
            attributes = {}
        elif 'attributes' not in attribute_payload:
            attributes = {}
        else:
            attributes = attribute_payload['attributes']
        thing = FakeThing(thing_name, thing_type, attributes, self.region_name)
        self.things[thing.arn] = thing
        return thing.thing_name, thing.arn

    def create_thing_type(self, thing_type_name, thing_type_properties):
        if thing_type_properties is None:
            thing_type_properties = {}
        thing_type = FakeThingType(thing_type_name, thing_type_properties, self.region_name)
        self.thing_types[thing_type.arn] = thing_type
        return thing_type.thing_type_name, thing_type.arn

    def list_thing_types(self, thing_type_name=None):
        if thing_type_name:
            # It's wierd but thing_type_name is filterd by forward match, not complete match
            return [_ for _ in self.thing_types.values() if _.thing_type_name.startswith(thing_type_name)]
        thing_types = self.thing_types.values()
        return thing_types

    def list_things(self, attribute_name, attribute_value, thing_type_name):
        # TODO: filter by attributess or thing_type
        things = self.things.values()
        return things

    def describe_thing(self, thing_name):
        things = [_ for _ in self.things.values() if _.thing_name == thing_name]
        if len(things) == 0:
            raise ResourceNotFoundException()
        return things[0]

    def describe_thing_type(self, thing_type_name):
        thing_types = [_ for _ in self.thing_types.values() if _.thing_type_name == thing_type_name]
        if len(thing_types) == 0:
            raise ResourceNotFoundException()
        return thing_types[0]

    def delete_thing(self, thing_name, expected_version):
        # TODO: handle expected_version

        # can raise ResourceNotFoundError
        thing = self.describe_thing(thing_name)
        del self.things[thing.arn]

    def delete_thing_type(self, thing_type_name):
        # can raise ResourceNotFoundError
        thing_type = self.describe_thing_type(thing_type_name)
        del self.thing_types[thing_type.arn]

    def update_thing(self, thing_name, thing_type_name, attribute_payload, expected_version, remove_thing_type):
        # if attributes payload = {}, nothing
        thing = self.describe_thing(thing_name)
        thing_type = None

        if remove_thing_type and thing_type_name:
            raise InvalidRequestException()

        # thing_type
        if thing_type_name:
            thing_types = self.list_thing_types()
            filtered_thing_types = [_ for _ in thing_types if _.thing_type_name == thing_type_name]
            if len(filtered_thing_types) == 0:
                raise ResourceNotFoundException()
            thing_type = filtered_thing_types[0]
            thing.thing_type = thing_type

        if remove_thing_type:
            thing.thing_type = None

        # attribute
        if attribute_payload is not None and 'attributes' in attribute_payload:
            do_merge = attribute_payload.get('merge', False)
            attributes = attribute_payload['attributes']
            if not do_merge:
                thing.attributes = attributes
            else:
                thing.attributes.update(attributes)
    def _random_string(self):
        n = 20
        random_str = ''.join([random.choice(string.ascii_letters + string.digits) for i in range(n)])
        return random_str

    def create_keys_and_certificate(self, set_as_active):
        # implement here
        # caCertificate can be blank
        key_pair = {
            'PublicKey': self._random_string(),
            'PrivateKey': self._random_string()
        }
        certificate_pem = self._random_string()
        status = 'ACTIVE' if set_as_active else 'INACTIVE'
        certificate = FakeCertificate(certificate_pem, status, self.region_name)
        self.certificates[certificate.certificate_id] = certificate
        return certificate, key_pair

    def delete_certificate(self, certificate_id):
        cert = self.describe_certificate(certificate_id)
        del self.certificates[certificate_id]

    def describe_certificate(self, certificate_id):
        certs = [_ for _ in self.certificates.values() if _.certificate_id == certificate_id]
        if len(certs) == 0:
            raise ResourceNotFoundException()
        return certs[0]

    def list_certificates(self):
        return self.certificates.values()

    def update_certificate(self, certificate_id, new_status):
        cert = self.describe_certificate(certificate_id)
        # TODO: validate new_status
        cert.status = new_status

    def create_policy(self, policy_name, policy_document):
        policy = FakePolicy(policy_name, policy_document, self.region_name)
        self.policies[policy.name] = policy
        return policy

    def list_policies(self):
        policies = self.policies.values()
        return policies

    def get_policy(self, policy_name):
        policies = [_ for _ in self.policies.values() if _.name == policy_name]
        if len(policies) == 0:
            raise ResourceNotFoundException()
        return policies[0]

    def delete_policy(self, policy_name):
        policy = self.get_policy(policy_name)
        del self.policies[policy.name]

    def _get_principal(self, principal_arn):
        """
        raise ResourceNotFoundException
        """
        if ':cert/' in principal_arn:
            certs = [_ for _ in self.certificates.values() if _.arn == principal_arn]
            if len(certs) == 0:
                raise ResourceNotFoundException()
            principal = certs[0]
            return principal
        else:
            # TODO: search for cognito_ids
            pass
        raise ResourceNotFoundException()

    def attach_principal_policy(self, policy_name, principal_arn):
        principal = self._get_principal(principal_arn)
        policy = self.get_policy(policy_name)
        k = (principal_arn, policy_name)
        if k in self.principal_policies:
            return
        self.principal_policies[k] = (principal, policy)

    def detach_principal_policy(self, policy_name, principal_arn):
        principal = self._get_principal(principal_arn)
        policy = self.get_policy(policy_name)

        k = (principal_arn, policy_name)
        if k not in self.principal_policies:
            raise ResourceNotFoundException()
        del self.principal_policies[k]

    def list_principal_policies(self, principal_arn):
        policies = [v[1] for k, v in self.principal_policies.items() if k[0] == principal_arn]
        return policies

    def list_policy_principals(self, policy_name):
        principals = [k[0] for k, v in self.principal_policies.items() if k[1] == policy_name]
        return principals

    def attach_thing_principal(self, thing_name, principal_arn):
        principal = self._get_principal(principal_arn)
        thing = self.describe_thing(thing_name)
        k = (principal_arn, thing_name)
        if k in self.principal_things:
            return
        self.principal_things[k] = (principal, thing)

    def detach_thing_principal(self, thing_name, principal_arn):
        principal = self._get_principal(principal_arn)
        thing = self.describe_thing(thing_name)
        k = (principal_arn, thing_name)
        if k not in self.principal_things:
            raise ResourceNotFoundException()
        del self.principal_things[k]

    def list_principal_things(self, principal_arn):
        thing_names = [k[0] for k, v in self.principal_things.items() if k[0] == principal_arn]
        return thing_names

    def list_thing_principals(self, thing_name):
        principals = [k[0] for k, v in self.principal_things.items() if k[1] == thing_name]
        return principals

available_regions = boto3.session.Session().get_available_regions("iot")
iot_backends = {region: IoTBackend(region) for region in available_regions}
