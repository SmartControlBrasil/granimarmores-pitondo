from django.urls import path

from scheduling import views

app_name = "scheduling"

urlpatterns = [
    path("", views.calendar_month, name="calendar"),
    path("dashboard/", views.schedule_dashboard, name="dashboard"),
    path("hoje/", views.calendar_today, name="today"),
    path("semana/", views.calendar_week, name="week"),
    path("mes/", views.calendar_month, name="month"),
    path("eventos/", views.event_list, name="event_list"),
    path("eventos/novo/", views.event_create, name="event_create"),
    path("eventos/<int:pk>/", views.event_detail, name="event_detail"),
    path("eventos/<int:pk>/confirmar/", views.event_confirm, name="event_confirm"),
    path("eventos/<int:pk>/tentativa/", views.event_confirm_attempt, name="event_confirm_attempt"),
    path("eventos/<int:pk>/iniciar/", views.event_start, name="event_start"),
    path("eventos/<int:pk>/concluir/", views.event_complete, name="event_complete"),
    path("eventos/<int:pk>/cancelar/", views.event_cancel, name="event_cancel"),
    path("eventos/<int:pk>/reagendar/", views.event_reschedule, name="event_reschedule"),
    path("eventos/<int:pk>/no-show/", views.event_no_show, name="event_no_show"),
    path("medicoes/", views.measurement_list, name="measurement_list"),
    path("leads/<int:pk>/agendar/", views.lead_schedule, name="lead_schedule"),
    path("pedidos/<int:pk>/agendar/", views.order_schedule, name="order_schedule"),
]
