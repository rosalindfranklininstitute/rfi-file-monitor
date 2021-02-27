---
layout: default
title: List of Operations

---

## List of Operations

<ul>
    {% for op in site.operations %}
        <li><a href="{{ op.url | relative_url }}">{{ op.title }}</a></li>
    {% endfor %}
</ul>