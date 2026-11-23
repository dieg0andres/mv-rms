from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("rms", "0008_research_intake")]

    operations = [
        migrations.AddField(
            model_name="researchintakeversion",
            name="prior_source_rights",
            field=models.JSONField(null=True),
        ),
        migrations.AddConstraint(
            model_name="researchintakeversion",
            constraint=models.CheckConstraint(
                condition=models.Q(state="ready") | models.Q(prior_source_rights__isnull=True),
                name="intake_prior_rights_ready_only",
            ),
        ),
    ]
