from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class ClassicalMusicPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            'meta': {
                'total_items': self.page.paginator.count,
                'total_pages': self.page.paginator.num_pages,
                'current_page': self.page.number,
                'page_size': len(data),
                'has_next': self.page.has_next(),
                'has_previous': self.page.has_previous(),
            },
            'links': {
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
            },
            'results': data
        })


class CustomMetaDataPagination(PageNumberPagination):
    page_size = 18
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "meta": {
                "total_items": self.page.paginator.count,
                "total_pages": self.page.paginator.num_pages,
                "current_page": self.page.number,
                "page_size": self.get_page_size(self.request),
                "has_next": self.page.has_next(),
                "has_previous": self.page.has_previous()
            },
            "links": {
                "next": self.get_next_link(),
                "previous": self.get_previous_link()
            },
            "results": data
        })