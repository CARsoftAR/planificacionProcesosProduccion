from django import forms
from .models import Feriado, MantenimientoMaquina

class MantenimientoMaquinaForm(forms.ModelForm):
    class Meta:
        model = MantenimientoMaquina
        fields = ['maquina', 'motivo', 'fecha_inicio', 'fecha_fin', 'estado', 'notas']
        widgets = {
            'maquina': forms.Select(attrs={'class': 'form-select'}),
            'motivo': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Cambio de rodamientos'}),
            'fecha_inicio': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'fecha_fin': forms.DateTimeInput(
                format='%Y-%m-%dT%H:%M',
                attrs={'class': 'form-control', 'type': 'datetime-local'}
            ),
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class FeriadoForm(forms.ModelForm):
    """
    Formulario para crear y editar feriados.
    """
    class Meta:
        model = Feriado
        fields = ['fecha', 'descripcion', 'tipo_jornada', 'activo']
        widgets = {
            'fecha': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'placeholder': 'Seleccione una fecha'
                }
            ),
            'descripcion': forms.TextInput(
                attrs={
                    'class': 'form-control',
                    'placeholder': 'Ej: Día de la Independencia',
                    'maxlength': '200'
                }
            ),
            'tipo_jornada': forms.Select(
                attrs={
                    'class': 'form-select'
                }
            ),
            'activo': forms.CheckboxInput(
                attrs={
                    'class': 'form-check-input'
                }
            ),
        }
        labels = {
            'fecha': 'Fecha del Feriado',
            'descripcion': 'Descripción',
            'tipo_jornada': 'Tipo de Jornada',
            'activo': 'Feriado activo',
        }
        help_texts = {
            'tipo_jornada': 'Indica si se trabaja completo, medio día o no se trabaja',
            'activo': 'Desmarque para desactivar temporalmente este feriado sin eliminarlo',
        }

    def clean_fecha(self):
        """
        Validación personalizada para la fecha.
        """
        fecha = self.cleaned_data.get('fecha')
        
        # Verificar que no exista otro feriado en la misma fecha (excepto si estamos editando)
        if fecha:
            existing = Feriado.objects.filter(fecha=fecha)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    f'Ya existe un feriado registrado para la fecha {fecha.strftime("%d/%m/%Y")}'
                )
        
        return fecha

