"""Thin authenticated adapters. Domain rules live in test_plan_services."""
import json
from django.http import HttpResponse
from rest_framework import exceptions
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from .hypothesis_api import ResearchRecordView, query_payload
from .test_plan_validation import TestPlanValidationError, issue
from . import test_plan_services as service


class StrictJSONParser(JSONParser):
    def parse(self,stream,media_type=None,parser_context=None):
        raw=stream.read(524289)
        if len(raw)>524288: raise TestPlanValidationError([issue('','too_large')])
        def pairs(items):
            out={}
            for key,value in items:
                if key in out: raise TestPlanValidationError([issue('','duplicate_json_key')])
                out[key]=value
            return out
        def nonfinite(value): raise ValueError('Invalid scalar')
        try: return json.loads(raw.decode('utf-8'),object_pairs_hook=pairs,parse_constant=nonfinite)
        except (ValueError,UnicodeError,RecursionError): raise exceptions.ParseError('The request is invalid.')


class TestPlanView(ResearchRecordView):
    parser_classes=[StrictJSONParser]
    action='collection'

    def get(self,request,plan_id=None,version_id=None,check_id=None):
        if self.action not in ('collection','checks') and request.query_params:
            raise TestPlanValidationError([issue('','unknown_field')])
        kwargs={'actor':request.user,'plan_id':plan_id}
        if self.action=='collection': body=service.list_test_plans(actor=request.user,query=query_payload(request.query_params))
        elif self.action=='detail': body=service.read_test_plan(**kwargs)
        elif self.action=='history': body=service.read_test_plan_history(**kwargs)
        elif self.action=='version': body=service.read_test_plan_version(**kwargs,version_id=version_id)
        elif self.action=='criterion': body=service.read_criterion_version(actor=request.user,version_id=version_id)
        elif self.action=='requirement': body=service.read_data_requirement_version(actor=request.user,version_id=version_id)
        elif self.action=='checks': body=service.list_data_access_checks(**kwargs,query=query_payload(request.query_params))
        elif self.action=='check': body=service.read_data_access_check(**kwargs,check_id=check_id)
        else: raise exceptions.MethodNotAllowed('GET')
        return Response(body)

    def post(self,request,plan_id=None,version_id=None,check_id=None):
        if self.action not in ('collection','correction','checks'): raise exceptions.MethodNotAllowed('POST')
        if request.query_params: raise TestPlanValidationError([issue('','unknown_field')])
        kwargs={'actor':request.user,'idempotency_key':request.headers.get('Idempotency-Key'),'payload':request.data}
        if self.action=='collection': stored=service.create_test_plan(**kwargs)
        elif self.action=='correction': stored=service.correct_test_plan(**kwargs,plan_id=plan_id)
        elif self.action=='checks': stored=service.record_data_access_check(**kwargs,plan_id=plan_id)
        else: raise exceptions.MethodNotAllowed('POST')
        return HttpResponse(stored.body,status=stored.status,content_type='application/json; charset=utf-8')
