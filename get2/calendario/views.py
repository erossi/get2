# Create your views here.

from django.http import HttpResponse, HttpResponseRedirect
from get2.calendario.models import *
from django.shortcuts import render_to_response
import calendar,datetime,locale
from django.db.models import Q, Count
from django.core.urlresolvers import reverse
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
import pdb
from django.template import RequestContext
from django.forms.formsets import formset_factory
import settings_calendario

####   persona   ####

def elenco_persona(request):
	#if request.user.is_staff:
	persone = Persona.objects.all().order_by('cognome')
	gruppi = Gruppo.objects.all()
	mansioni = Mansione.objects.all()
	risposta = HttpResponse(render_to_response('elenco_persona.html',{'persone':persone,'request':request,'gruppi':gruppi,'mansioni':mansioni}))
	return risposta
	#else:
	#	return render_to_response('staff-no.html')


def nuovo_persona(request):
	#if request.user.is_staff:
	azione = 'nuovo';
	if request.method == 'POST':
		form = PersonaForm(request.POST)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/calendario') 
	else:
		form = PersonaForm()
	return render_to_response('form_persona.html',{'form': form,'azione': azione,'mansione_form':MansioneForm()}, RequestContext(request))
	#else:
	#	return render_to_response('staff-no.html')

def modifica_persona(request,persona_id):
	azione = 'modifica'
	per = Persona.objects.get(id=persona_id)
	if request.method == 'POST': # If the form has been submitted...
		form = PersonaForm(request.POST, instance=per) # necessario per modificare la riga preesistente
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/persona/elenco') # Redirect after POST
	else:
		form = PersonaForm(instance=per)
	return render_to_response('form_persona.html',{'request': request, 'form': form,'azione': azione, 'per': per,'mansione_form':MansioneForm()}, RequestContext(request))

####   fine persona   ####

#####   calendario   ####

def calendario(request):
	if request.COOKIES.has_key('anno'):
		anno=int(request.COOKIES['anno'])
	else:
		anno=datetime.datetime.today().year

	if request.COOKIES.has_key('mese'):
		mese=int(request.COOKIES['mese'])
	else:
		mese=datetime.datetime.today().month

	if request.COOKIES.has_key('giorno'):
		giorno=int(request.COOKIES['giorno'])
	else:
		giorno=datetime.datetime.today().day

	start=datetime.datetime(anno,mese,giorno,1)
	giorni = []
	turni = []
	for i in range(0,7):
		giorni.append(start)
		stop = start + datetime.timedelta(days=1)
		turni.append(Turno.objects.filter(inizio__range=(start, stop)).order_by('inizio'))
		start = start + datetime.timedelta(days=1)
	start = datetime.datetime(anno,mese,giorno,1)
	
	calendario = []
	calendario.append(giorni)
	calendario.append(turni)
	calendario=zip(*calendario)
	tipo_turno=TipoTurno.objects.all()
	corpo=render_to_response('calendario.html',{'calendario':calendario,'start':start,'request':request,'tipo_turno':tipo_turno})
	risposta = HttpResponse(corpo)
	risposta.set_cookie('anno', value=anno)
	risposta.set_cookie('mese', value=mese)
	risposta.set_cookie('giorno', value=giorno)
	risposta.set_cookie('sezione', value='calendario')
	return risposta

def calendarioazione(request,azione):
	start = datetime.datetime(int(request.COOKIES['anno']),int(request.COOKIES['mese']),int(request.COOKIES['giorno']))
	if azione == 'oggi':
		start = datetime.datetime.today()
	if azione == 'avanti':
		start += datetime.timedelta(days=1)
	if azione == 'indietro':
		start -= datetime.timedelta(days=1)
	if azione == 'settavanti':
		start += datetime.timedelta(days=7)
	if azione == 'settindietro':
		start -= datetime.timedelta(days=7)
	risposta = HttpResponseRedirect('/calendario/')
	risposta.set_cookie('anno', value=start.year)
	risposta.set_cookie('mese', value=start.month)
	risposta.set_cookie('giorno', value=start.day)
	return risposta

####   fine calendario   ####

####   disponibilita   ####

def disponibilita_verifica_tempo(request, turno):
	if request.user.is_staff:
		verifica=True
		errore=''
	else:
		now=datetime.datetime.now()
		diff=turno.inizio-now
		if diff<0:
			verifica=False
			errore='passato'
		elif diff<DISP_MIN:
			verifica=False
			errore='vicino'
		elif diff>DISP_MAX:
			verifica=False
			errore='lontano'
		else:
			verifica=True
			errore=''
	return (verifica,errore)


def disponibilita_risolvi_contemporaneo(request,persona_id,contemporaneo):
	if Disponibilita.objects.filter(persona_id=persona_id,turno=contemporaneo).exist():
		for d in Disponibilita.objects.filter(persona_id=persona_id,turno=contemporaneo):
			if d.tipo=="Disponibile":
				persona= Persona.objects.get(id=persona_id)
				notifica_disponibilita(request,persona,contemporaneo,'Non piu disponibile',contemporaneo.mansione)
			d.delete()


def nuovo_disponibilita(request, tipo_disponibilita, persona_id, user_id, turno_id, mansione_id):
	#inizializzo ma non salvo un oggetto disponibilita
	disponibilita=Disponibilita()
	disponibilita.tipo=tipo_disponibilita
	disponibilita.persona=Persona.objects.get(id=persona_id)
	disponibilita.ultima_modifica=datetime.datetime.now()
	disponibilita.creata_da=User.objects.get(id=user_id)
	disponibilita.turno=Turno.objects.get(id=turno_id)
	disponibilita.mansione=Mansione.objects.get(id=mansione_id)
	#verifico se la disponibilita e entro i tempi corretti
	if disponibilita_verifica_tempo(request, disponibilita.turno)[0]:
		#una persona puo avere una sola disponibilita per turno
		if Disponibilita.objects.filter(persona=disponibilita.persona,turno=disponibilita.turno ).exists():
			esistente=Disponibilita.objects.get(persona=disponibilita.persona, turno=disponibilita.turno )
			if esistente.tipo=='Disponibile':
				notifica_disponibilita(request,esistente.persona,esistente.turno,'Non piu disponibile',esistente.mansione)
			esistente.delete()
		#risolvo i conflitti con i turni contemporanei
		for contemporaneo in disponibilita.turno.contemporanei():
			disponibilita_risolvi_contemporaneo(persona_id,contemporaneo)
		disponibilita.save()
		if not request.user.is_staff:
			notifica_disponibilita(request,disponibilita.persona,disponibilita.turno,tipo_disponibilita,disponibilita.mansione)

####   fine disponibilita   ####

####   notifica   ####

def notifica_disponibilita(request,persona,turno,tipo_disponibilita,mansione):
	for n in NOTIFICHE:
		if turno.inizio.weekday() in n['giorni']:
			messaggio=str(persona) + ' si e reso <b>' + str(tipo_disponibilita) + '</b> con mansione di <b>'+ str(mansione) +'</b> per il turno <b>' + 'turno' + '</b>'
			now=datetime.datetime.now()
			notifica=Notifica()
			notifica.testo=messaggio
			notifica.data=now
			notifica.letto=False
			destinatario_id=n['id_utente']
			notifica.destinatario_id=destinatario_id
			notifica.save()
	return True

def elenco_notifica(request):
	u=request.user
	notifiche=Notifica.objects.filter(destinatario=u).order_by('data').reverse()
	return render_to_response('notifiche.html',{'notifiche':notifiche,'request':request})

####   fine notifica   ####

####   inizio utenti   ####

def elenco_utente(request):
	#if request.user.is_staff:
	utenti = User.objects.all()
	persone = Persona.objects.all()
	risposta = HttpResponse(render_to_response('elenco_utente.html',{'utenti':utenti,'persone':persone,'request':request,}))
	return risposta
	#else:
	#	return render_to_response('staff-no.html')

def nuovo_utente(request):
	#if request.user.is_staff:
	# Do something for anonymous users.
	azione = 'nuovo';
	if request.method == 'POST': # If the form has been submitted...
		form = UserCreationForm2(request.POST) # A form bound to the POST data
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/utente/elenco') # Redirect after POST
	else:
		form = UserCreationForm2()
	return render_to_response('form_utente.html',{'request':request, 'form': form,'azione': azione}, RequestContext(request))

def modifica_utente(request,utente_id):
	azione = 'modifica'
	user = User.objects.get(id=utente_id)
	if request.method == 'POST': # If the form has been submitted..
		form = UserChangeForm2(request.POST, instance=user,)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/utente/elenco') # Redirect after POST
	else:
		form = UserChangeForm2(instance=user)
	return render_to_response('form_utente.html',{'request':request, 'form': form,'azione': azione, 'user': user,}, RequestContext(request))

def modifica_password_utente(request,utente_id):
	user = User.objects.get(id=utente_id)
	if request.method == 'POST': # If the form has been submitted...
		form = AdminPasswordChangeForm(user=user, data=request.POST)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/utente/elenco') # Redirect after POST
	else:
		form = AdminPasswordChangeForm(user=user)
	return render_to_response('form_password_utente.html',{'request':request, 'form': form, 'user': user,}, RequestContext(request))
	
####   fine utenti   ####

#### inzio tipo turno ####

def elenco_tipo_turno(request):
	tipi_turno=TipoTurno.objects.all()
	return render_to_response('elenco_tipo_turno.html',{'tipi_turno':tipi_turno,'tipo_turno_form':TipoTurnoForm(),'operatori':OPERATORI,'mansioni':Mansione.objects.all(),'request':request}, RequestContext(request))

#### fine tipo turno ####